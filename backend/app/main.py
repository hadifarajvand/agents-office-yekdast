"""FastAPI app: serves the office page and the /api/* contract the frontend uses.

Request hygiene (the API drives agents and spends model budget, so it is never open):
  - Host must be one of config.api.allowed_hosts (blocks DNS-rebinding);
  - a browser Origin, when sent, must be one of those hosts;
  - every state-changing request carries X-AO-Client (a custom header a cross-site
    form or simple fetch cannot send without a CORS preflight, which this app refuses);
  - when AO_API_TOKEN is set, every /api request also needs X-AO-Token (the page gets
    it in a <meta> tag only when served from an allowed host);
  - bodies of state-changing requests must be JSON objects;
  - errors return a generic message; details go to the server log.

Task fields the frontend reads (src/tasks.js): addedAt, startedAt, waitingAt, doneAt
(ms since epoch), approved, draft, ask, result, read, tools, used, model*/effort*.
"""
from __future__ import annotations

import asyncio
import logging
import os
import time
from contextlib import asynccontextmanager
from urllib.parse import urlsplit

from fastapi import FastAPI, Request
from fastapi.responses import FileResponse, HTMLResponse, JSONResponse
from langgraph.checkpoint.postgres.aio import AsyncPostgresSaver

from . import db, learn, llm, routines as routines_mod, when as whenmod
from .brain import brain_graph, brain_summary
from .config import ROOT, load_config
from .graph import engine
from .mcp import registry as mcp_registry
from .models import EFFORT_KEYS, MODEL_KEYS, MODELS, model_id
from .onboard import active as onboard_active, setup_map
from .roster import DEPTS, load_roster
from .skills import load_skills

log = logging.getLogger("agents_office")

HTML = ROOT / "dist" / "command-centre-v2.html"
VERSION = "0.1.0"

cfg = load_config()
mcp_registry.configure({"mcp": cfg.mcp, "tools": cfg.tools}, valid_depts=set(DEPTS.keys()))

_roster_cache: dict = {}
_skills_cache = None
_bg_tasks: set[asyncio.Task] = set()
_run_slots = asyncio.Semaphore(int(os.environ.get("AO_PARALLEL_RUNS", "2")))


def spawn(coro) -> asyncio.Task:
    """Start background work and keep a reference so it is not garbage-collected."""
    t = asyncio.create_task(coro)
    _bg_tasks.add(t)
    t.add_done_callback(_bg_tasks.discard)
    return t


async def _record_cost(call: "llm.Call", label: str) -> None:
    await db.record_cost(label, call.model_pinned, call.model_seen, call.input_tokens, call.output_tokens, call.usd)


@asynccontextmanager
async def lifespan(_app: FastAPI):
    pool = await db.open_pool()
    saver = AsyncPostgresSaver(pool)
    await saver.setup()
    engine.compile_graph(checkpointer=saver)
    try:
        from .pipeline import graph as pipeline_graph
        pipeline_graph.compile_pipeline(checkpointer=saver)
    except ImportError:
        pass
    llm.on_usage(_record_cost)
    n = await db.fail_interrupted_tasks()
    if n:
        log.warning("marked %d task(s) interrupted by the last restart as failed", n)
    ticker = spawn(_tick_routines())
    try:
        yield
    finally:
        ticker.cancel()
        for t in list(_bg_tasks):
            t.cancel()
        await db.close_pool()


app = FastAPI(lifespan=lifespan, docs_url=None, redoc_url=None, openapi_url=None)


# ---------- request hygiene ----------

def _allowed_hosts() -> set[str]:
    extra = [h.strip() for h in os.environ.get("AO_ALLOWED_HOSTS", "").split(",") if h.strip()]
    return set(cfg.api.get("allowed_hosts") or []) | set(extra)


def _host_only(value: str) -> str:
    v = value.strip().lower()
    if v.startswith("["):
        return v.split("]")[0] + "]"
    return v.rsplit(":", 1)[0] if v.count(":") == 1 else v


MUTATING = {"POST", "PUT", "PATCH", "DELETE"}


@app.middleware("http")
async def guard(request: Request, call_next):
    hosts = _allowed_hosts()
    host = _host_only(request.headers.get("host", ""))
    if host not in hosts:
        return JSONResponse({"error": "host not allowed"}, status_code=403)
    origin = request.headers.get("origin")
    if origin and _host_only(urlsplit(origin).netloc) not in hosts:
        return JSONResponse({"error": "origin not allowed"}, status_code=403)
    if request.url.path.startswith("/api/"):
        token = cfg.secret("api", "token_env")
        if token and request.headers.get("x-ao-token") != token:
            return JSONResponse({"error": "missing or wrong X-AO-Token"}, status_code=401)
        if request.method in MUTATING:
            if request.headers.get("x-ao-client") != "office":
                return JSONResponse({"error": "missing X-AO-Client header"}, status_code=403)
            ctype = request.headers.get("content-type", "")
            length = request.headers.get("content-length")
            has_body = (length not in (None, "0")) or request.headers.get("transfer-encoding")
            if has_body and not ctype.startswith("application/json"):
                return JSONResponse({"error": "body must be application/json"}, status_code=415)
    return await call_next(request)


async def body_of(req: Request) -> dict:
    """The JSON body as a dict; {} when absent. A non-object body is a 400."""
    raw = await req.body()
    if not raw.strip():
        return {}
    try:
        import json
        data = json.loads(raw)
    except ValueError:
        raise BadRequest("body is not valid JSON")
    if not isinstance(data, dict):
        raise BadRequest("body must be a JSON object")
    return data


class BadRequest(Exception):
    pass


@app.exception_handler(BadRequest)
async def on_bad_request(_req, exc: BadRequest):
    return JSONResponse({"error": str(exc)}, status_code=400)


@app.exception_handler(Exception)
async def on_error(req: Request, exc: Exception):
    log.exception("unhandled error on %s %s", req.method, req.url.path)
    return JSONResponse({"error": "internal error — see the server log"}, status_code=500)


# ---------- roster, skills ----------

def reload_roster() -> dict:
    global _roster_cache
    _roster_cache = load_roster(cfg.brain_path)
    return _roster_cache


def refresh_skills():
    global _skills_cache
    _skills_cache = load_skills(cfg.brain_path, reload_roster()["agents"])
    return _skills_cache


reload_roster()
refresh_skills()


def agents_list():
    return _roster_cache["agents"]


def find_agent(agent_id: str):
    return next((a for a in agents_list() if a.id == agent_id), None)


def approves_of(agent_id: str) -> list[str]:
    """Stages this seat signs off, from config.pipeline.stages and config.exposure.keys."""
    out = [s["name"] for s in cfg.pipeline.get("stages", []) if s.get("lead") == agent_id and s["name"] != "exposure"]
    if agent_id in (cfg.exposure.get("keys") or {}).values():
        out.append("exposure")
    return out


def agents_out():
    sm = setup_map(list(DEPTS.keys()), agents_list(), _skills_cache)
    return [
        {
            "id": a.id, "department": a.department, "lead": a.lead, "name": a.name,
            "role": a.role, "does": a.does, "tools": a.tools, "model": a.model, "effort": a.effort,
            "approves": approves_of(a.id), "setUp": sm.get(a.department, False),
        }
        for a in agents_list()
    ]


def now_ms() -> float:
    return time.time() * 1000


# ---------- static frontend ----------

def _page(dark: bool = False) -> HTMLResponse:
    if not HTML.exists():
        return HTMLResponse("<h1>build the frontend first: npm run build</h1>", 500)
    text = HTML.read_text()
    token = cfg.secret("api", "token_env")
    meta = f'<meta name="ao-token" content="{token}">' if token else ""
    text = text.replace("<head>", f"<head>{meta}", 1)
    if dark:
        text = text.replace("<body>", '<body class="dark">', 1)
    return HTMLResponse(text, headers={"Cache-Control": "no-store", "X-Frame-Options": "DENY",
                                       "Referrer-Policy": "no-referrer"})


@app.get("/", response_class=HTMLResponse)
@app.get("/command-centre-v2.html", response_class=HTMLResponse)
async def root():
    return _page()


@app.get("/dark", response_class=HTMLResponse)
async def dark():
    return _page(dark=True)


# ---------- read-only info ----------

def pipeline_info() -> dict:
    return {"stages": cfg.pipeline.get("stages", []), "deadlineDays": cfg.pipeline.get("deadline_days", 3),
            "exposure": {"tier1OwnerClicks": cfg.exposure.get("tier1_owner_clicks", 3),
                         "previewTtlDays": cfg.exposure.get("preview_ttl_days", 7),
                         "keys": cfg.exposure.get("keys", {})}}


@app.get("/api/health")
async def health():
    rl = routines_mod.load(cfg.brain_path, agents_list())
    skills = refresh_skills()
    return {
        "ok": True, "version": VERSION, "backend": "langgraph", "model": cfg.model,
        "modelName": MODELS[cfg.model].name if cfg.model in MODELS else cfg.model,
        "modelId": model_id(cfg.model), "models": MODEL_KEYS, "effort": None, "efforts": EFFORT_KEYS,
        "roles": cfg.roles, "router": {"format": cfg.router.get("format"), "baseUrl": cfg.router.get("base_url")},
        "name": cfg.name, "brain": str(cfg.brain_path), "notes": brain_summary(cfg.brain_path)["notes"],
        "depts": list(DEPTS.keys()), "agents": agents_out(), "agentCount": len(agents_list()),
        "setup": setup_map(list(DEPTS.keys()), agents_list(), skills),
        "routines": {"count": len(rl["routines"]), "paused": sum(1 for r in rl["routines"] if r["paused"]),
                     "depts": routines_mod.ALLOWED, "problems": rl["problems"]},
        "roster": {"customised": _roster_cache["customised"], "briefed": _roster_cache["briefed"],
                   "files": _roster_cache["files"], "problems": _roster_cache["problems"]},
        "skills": skills.summary(),
        "tools": {"web": bool(cfg.tools.get("web")) and mcp_registry.web_bound},
        "mcp": mcp_registry.summary(),
        "pipeline": pipeline_info(),
        "worker": cfg.worker.get("kind"),
        "config": {"problems": cfg.problems},
    }


@app.get("/api/agents")
async def get_agents():
    reload_roster()
    return {"agents": agents_out(), "problems": _roster_cache["problems"], "files": _roster_cache["files"]}


@app.get("/api/skills")
async def get_skills():
    return refresh_skills().summary()


@app.get("/api/lessons")
async def get_lessons():
    out = []
    for a in agents_list():
        r = learn.read(cfg.brain_path, a.id)
        if r.get("rules") or r.get("oneOffs"):
            out.append({"agent": a.id, "name": a.name, **r})
    return {"dir": str(learn.dir_(cfg.brain_path)), "agents": out}


@app.get("/api/mcp")
async def get_mcp(refresh: int = 0):
    if refresh:
        await mcp_registry.discover()
    return {**mcp_registry.summary(), "tools": True}


@app.get("/api/brain")
async def get_brain():
    return brain_graph(cfg.brain_path)


@app.get("/api/usage")
async def get_usage(refresh: int = 0):
    """The office's own count of model calls in the last five hours (from run_costs).
    9router's own cost figures are estimates and are not used."""
    w = await db.usage_window(5.0)
    return {"ok": True, "source": "office", "window": w}


# ---------- tasks ----------

@app.get("/api/tasks")
async def list_tasks():
    return await db.list_tasks()


@app.post("/api/tasks")
async def create_task(req: Request):
    body = await body_of(req)
    dept = body.get("dept")
    text = str(body.get("text") or "").strip()
    if dept not in DEPTS or not text:
        return JSONResponse({"error": "dept and text are required"}, status_code=400)
    if len(text) > 20000:
        return JSONResponse({"error": "task text is too long (20,000 characters max)"}, status_code=400)
    routed = await engine.route(dept, text, agents_list())
    t = now_ms()
    task = {
        "id": db.nid(), "dept": dept, "text": text, "by": "you", "state": "next",
        "agent": routed["agent"], "title": routed["title"], "plan": routed["plan"],
        "eta_minutes": routed["eta_minutes"], "why": routed["why"], "needsOk": bool(routed["needs_ok"]),
        "createdAt": t, "addedAt": t, "runs": 0,
    }
    for key, valid in (("model", MODEL_KEYS), ("effort", EFFORT_KEYS)):
        v = body.get(key)
        if v not in (None, ""):
            if v not in valid:
                return JSONResponse({"error": f"{key} must be one of {', '.join(valid)}"}, status_code=400)
            task[key] = v
    await db.save_task(task)
    return task


def _new_thread(task: dict) -> str:
    task["runs"] = int(task.get("runs") or 0) + 1
    task["thread"] = f'{task["id"]}-{task["runs"]}'
    return task["thread"]


def _apply_run(task: dict, out: dict) -> None:
    task.update(skills=out.get("skills", []), read=out.get("read", []), tools=out.get("tools", []),
                used=out.get("tools", []), modelUsed=out.get("modelUsed"), modelFrom=out.get("modelFrom"),
                effortUsed=out.get("effortUsed"), effortFrom=out.get("effortFrom"), cost=out.get("meter"))
    if out.get("paused"):
        task.update(state="waiting", draft=out.get("draft") or out.get("result", ""),
                    waitingAt=now_ms(), ask=routines_mod.ask_line(task))
    else:
        task.update(state="done", result=out.get("result", ""), doneAt=now_ms())


async def _execute(task: dict, feedback: str | None, mode: str | None) -> dict:
    agent = find_agent(task["agent"])
    return await engine.run_task(task, feedback, mode, agent, agents_list(), refresh_skills(), cfg.brain_path, cfg.model, None)


async def _learn(task: dict, feedback: str) -> None:
    agent = find_agent(task["agent"])
    if not agent or not feedback:
        return
    verdict = await learn.classify(engine.ask, agent, task, feedback)
    learn.record(cfg.brain_path, agent, task, feedback, verdict)


@app.post("/api/tasks/{task_id}/run")
@app.post("/api/tasks/{task_id}/revise")
async def run_or_revise_task(task_id: str, req: Request):
    """Blocks until the run finishes. A task that needs the owner's OK comes back
    "waiting" with a draft instead of "done"."""
    body = await body_of(req)
    feedback = body.get("feedback")
    task = await db.get_task(task_id)
    if not task:
        return JSONResponse({"error": "not found"}, status_code=404)
    if task.get("state") in ("doing", "waiting"):
        return JSONResponse({"error": f'task is already {task["state"]}'}, status_code=409)
    task.update(state="doing", startedAt=now_ms())
    _new_thread(task)
    await db.save_task(task)
    async with _run_slots:
        try:
            out = await _execute(task, feedback, "draft" if task.get("needsOk") else None)
            _apply_run(task, out)
        except Exception as e:
            log.exception("task %s failed", task_id)
            task.update(state="done", error=True, result=f"The run failed: {type(e).__name__}.", doneAt=now_ms())
    await db.save_task(task)
    if feedback:
        spawn(_learn(task, feedback))
    return task


@app.post("/api/tasks/{task_id}/approve")
@app.post("/api/tasks/{task_id}/reject")
async def approve_or_reject_task(task_id: str, req: Request):
    """Acknowledges at once; the agent's follow-up runs in the background. The
    waiting -> doing move is atomic, so a second click is refused, never re-run."""
    is_approve = req.url.path.endswith("/approve")
    body = await body_of(req)
    feedback = None if is_approve else (str(body.get("feedback") or "").strip() or None)
    task = await db.claim_task(task_id, "waiting", "doing")
    if not task:
        return JSONResponse({"error": "task is not waiting for approval"}, status_code=400)
    spawn(_resume(task_id, is_approve, feedback))
    return {"ok": True, "id": task_id, "state": "doing"}


async def _resume(task_id: str, is_approve: bool, feedback: str | None) -> None:
    t = await db.get_task(task_id)
    if not t:
        return
    async with _run_slots:
        try:
            out = await engine.resume_task(t.get("thread") or task_id, "approve" if is_approve else "draft",
                                           feedback, refresh_skills(), find_agent(t["agent"]))
            if is_approve:
                t.update(result=out.get("result", ""), state="done", approved=True, approvedAt=now_ms(), doneAt=now_ms())
            else:
                t.update(draft=out.get("draft") or out.get("result", ""), state="waiting", waitingAt=now_ms(),
                         ask=routines_mod.ask_line(t), revised=True)
        except Exception as e:
            log.exception("resuming task %s failed", task_id)
            t.update(state="done", error=True, result=f"The follow-up failed: {type(e).__name__}.", doneAt=now_ms())
        await db.save_task(t)
    if feedback:
        await _learn(t, feedback)


@app.delete("/api/tasks/{task_id}")
async def delete_task(task_id: str):
    await db.delete_task(task_id)
    return {"ok": True}


# ---------- routines ----------

async def _routines_out():
    rl = routines_mod.load(cfg.brain_path, agents_list())
    st = await db.load_routine_state()
    merged = routines_mod.with_state(rl["routines"], st)
    return {"routines": merged["list"], "depts": routines_mod.ALLOWED, "path": str(rl["path"]), "problems": rl["problems"]}


@app.get("/api/routines")
async def get_routines():
    return await _routines_out()


@app.post("/api/routines")
async def create_routine(req: Request):
    body = await body_of(req)
    dept = body.get("dept")
    if dept not in DEPTS:
        return JSONResponse({"error": "unknown department"}, status_code=400)
    if dept not in routines_mod.ALLOWED:
        return JSONResponse({"error": routines_mod.refusal(dept)}, status_code=400)
    text = str(body.get("text") or "").strip()
    if not text:
        return JSONResponse({"error": "no task text"}, status_code=400)
    when = body.get("when")
    guessed = None
    if not when:
        parsed = whenmod.parse_when(text)
        when = parsed["when"] if parsed else None
        guessed = parsed.get("guessWord") if parsed and parsed.get("guessed") else None
    if not whenmod.valid(when):
        return JSONResponse({"error": "could not work out a schedule — include a day/time"}, status_code=400)
    agent_id = body.get("agent")
    if not agent_id:
        routed = await engine.route(dept, text, agents_list())
        agent_id = routed["agent"]
    rl = routines_mod.load(cfg.brain_path, agents_list())
    draft = {"dept": dept, "agent": agent_id, "text": text, "title": body.get("title") or text[:90],
             "when": when, "needsOk": body.get("needsOk", routines_mod.guess_needs_ok(text)), "paused": False}
    for k in ("model", "effort", "id"):
        if body.get(k):
            draft[k] = body[k]
    v = routines_mod.validate(draft, agents_list(), rl["routines"])
    if v["problems"]:
        return JSONResponse({"error": "; ".join(v["problems"])}, status_code=400)
    routines_mod.save(cfg.brain_path, rl["routines"] + [v["routine"]], rl["invalid"])
    out = {**v["routine"], "desc": whenmod.describe(v["routine"]["when"]),
           "nextAt": None if v["routine"]["paused"] else whenmod.next_run(v["routine"]["when"], now_ms())}
    return {"ok": True, "routine": out, "guessed": guessed}


def _find_routine(rl: dict, routine_id: str) -> dict | None:
    return next((x for x in rl["routines"] if x["id"] == routine_id), None)


@app.post("/api/routines/{routine_id}/run")
async def run_routine_now(routine_id: str):
    rl = routines_mod.load(cfg.brain_path, agents_list())
    r = _find_routine(rl, routine_id)
    if not r:
        return JSONResponse({"error": "not found"}, status_code=404)
    task = await _fire_routine(r, late=False)
    return {"ok": True, "task": task}


@app.post("/api/routines/{routine_id}/pause")
@app.post("/api/routines/{routine_id}/resume")
async def pause_resume_routine(routine_id: str, req: Request):
    paused = req.url.path.endswith("/pause")
    rl = routines_mod.load(cfg.brain_path, agents_list())
    if not _find_routine(rl, routine_id):
        return JSONResponse({"error": "not found"}, status_code=404)
    out = [{**r, "paused": paused} if r["id"] == routine_id else r for r in rl["routines"]]
    routines_mod.save(cfg.brain_path, out, rl["invalid"])
    return {"ok": True}


@app.post("/api/routines/{routine_id}")
async def patch_routine(routine_id: str, req: Request):
    body = await body_of(req)
    rl = routines_mod.load(cfg.brain_path, agents_list())
    cur = _find_routine(rl, routine_id)
    if not cur:
        return JSONResponse({"error": "not found"}, status_code=404)
    patch = {k: v for k, v in body.items() if k in ("needsOk", "paused", "text", "title", "when", "model", "effort")}
    others = [r for r in rl["routines"] if r["id"] != routine_id]
    v = routines_mod.validate({**cur, **patch}, agents_list(), others)
    if v["problems"]:
        return JSONResponse({"error": "; ".join(v["problems"])}, status_code=400)
    routines_mod.save(cfg.brain_path, [v["routine"] if r["id"] == routine_id else r for r in rl["routines"]], rl["invalid"])
    return {"ok": True}


@app.delete("/api/routines/{routine_id}")
async def delete_routine(routine_id: str):
    rl = routines_mod.load(cfg.brain_path, agents_list())
    routines_mod.save(cfg.brain_path, [r for r in rl["routines"] if r["id"] != routine_id], rl["invalid"])
    return {"ok": True}


async def _fire_routine(r: dict, late: bool) -> dict:
    st = await db.load_routine_state()
    t = now_ms()
    task = {
        "id": db.nid(), "dept": r["dept"], "agent": r["agent"], "text": r["text"], "title": r["title"],
        "plan": r.get("plan", []), "by": "routine", "state": "next", "routine": r["id"],
        "when": r["when"], "due": t, "late": late, "needsOk": r["needsOk"],
        "routineModel": r.get("model"), "routineEffort": r.get("effort"), "createdAt": t, "addedAt": t, "runs": 0,
    }
    await db.save_task(task)
    routines_mod.advance(st, r, task_id=task["id"], late=late)
    await db.save_routine_state(st)
    spawn(_run_server_task(task["id"]))
    return task


async def _run_server_task(task_id: str):
    task = await db.get_task(task_id)
    if not task:
        return
    task.update(state="doing", startedAt=now_ms())
    _new_thread(task)
    await db.save_task(task)
    async with _run_slots:
        try:
            out = await _execute(task, None, "draft" if task.get("needsOk") else "routine")
            _apply_run(task, out)
        except Exception as e:
            log.exception("routine task %s failed", task_id)
            task.update(state="done", error=True, result=f"The run failed: {type(e).__name__}.", doneAt=now_ms())
    await db.save_task(task)


async def _tick_routines():
    """Every 20 s: fire routines that are due. A due slot is claimed in Postgres
    first, so two office processes never fire the same run twice."""
    while True:
        try:
            rl = routines_mod.load(cfg.brain_path, agents_list())
            st = await db.load_routine_state()
            merged = routines_mod.with_state(rl["routines"], st)
            if merged["changed"]:
                await db.save_routine_state(st)
            for hit in routines_mod.due(rl["routines"], st):
                if await db.claim_routine_slot(hit["routine"]["id"], hit["due"]):
                    await _fire_routine(hit["routine"], hit["late"])
        except asyncio.CancelledError:
            raise
        except Exception:
            log.exception("routine tick failed")
        try:
            from .pipeline.janitor import expire_previews
            from .pipeline.ports import get_deps
            get_deps()  # only when the pipeline is configured
            await expire_previews()
        except asyncio.CancelledError:
            raise
        except RuntimeError:
            pass
        except Exception:
            log.exception("preview expiry failed")
        await asyncio.sleep(20)


# ---------- chat ----------

def _command(text: str) -> tuple[str, str] | None:
    """Routine commands need an explicit form, so ordinary sentences ("schedule a
    call", "running low on cash") are never mistaken for one:
      "routines" · "pause routine <words>" · "resume routine <words>" ·
      "run routine <words>" · "delete routine <words>"."""
    t = text.strip().lower()
    if t in ("routines", "list routines", "show routines"):
        return ("list", "")
    for verb in ("pause", "resume", "run", "delete"):
        prefix = f"{verb} routine "
        if t.startswith(prefix):
            return (verb, t[len(prefix):])
    return None


@app.post("/api/chat")
async def chat(req: Request):
    body = await body_of(req)
    agent = find_agent(body.get("agent"))
    text = str(body.get("text") or "").strip()[:8000]
    history = body.get("history") if isinstance(body.get("history"), list) else []
    if not agent:
        return JSONResponse({"error": "unknown agent"}, status_code=400)

    cmd = None if onboard_active(ROOT / "data", agent.department) else _command(text)
    if cmd:
        verb, words = cmd
        rl = routines_mod.load(cfg.brain_path, agents_list())
        if verb == "list":
            return {"reply": routines_mod.list_text(rl["routines"], agent.department, agents_list()), "routines": True}
        m = routines_mod.match_routine(rl["routines"], agent.department, words)
        if not m:
            return {"reply": f'No routine in this department matches "{words}". Say "routines" to see them.'}
        if verb == "delete":
            routines_mod.save(cfg.brain_path, [r for r in rl["routines"] if r["id"] != m["id"]], rl["invalid"])
        elif verb in ("pause", "resume"):
            routines_mod.save(cfg.brain_path, [{**r, "paused": verb == "pause"} if r["id"] == m["id"] else r
                                               for r in rl["routines"]], rl["invalid"])
        else:
            await _fire_routine(m, late=False)
        done = {"pause": "paused", "resume": "resumed", "run": "started", "delete": "deleted"}[verb]
        return {"reply": f'Done — "{m["title"]}" {done}.', "routines": True}

    reply = await engine.chat(agent, text, history, agents_list(), refresh_skills(), cfg.brain_path, cfg.model, None)
    return {"reply": reply, "routines": False, "read": [], "tools": []}


try:  # the job pipeline (Phase 2) mounts its own router
    from .pipeline.api import router as pipeline_router
    app.include_router(pipeline_router)
except ImportError:
    pass
