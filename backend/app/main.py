"""FastAPI app implementing the exact /api/* contract from serve.mjs, backed by the
LangGraph engine (app/graph/engine.py) instead of a single CLI/SDK call. The existing
frontend (dist/command-centre-v2.html) is served unmodified and needs no changes:
same routes, same request/response shapes, same polling + blocking/async-ack behavior.
"""
from __future__ import annotations

import asyncio
import time
from pathlib import Path

from fastapi import FastAPI, Request
from fastapi.responses import FileResponse, HTMLResponse, JSONResponse

from . import db, learn, routines as routines_mod, when as whenmod
from .brain import brain_summary
from .config import ROOT, load_config
from .graph import engine
from .mcp import registry as mcp_registry
from .models import EFFORT_KEYS, MODEL_KEYS, MODELS
from .onboard import active as onboard_active, is_set_up, setup_map
from .roster import DEPTS, load_roster
from .skills import load_skills

app = FastAPI()
cfg = load_config()
mcp_registry.configure({"mcp": cfg.mcp, "tools": cfg.tools}, valid_depts=set(DEPTS.keys()))

HTML = ROOT / "dist" / "command-centre-v2.html"
VERSION = "4.0.0-langgraph"

_roster_cache: dict = {}
_skills_cache = None
_run_lock = asyncio.Lock()


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


def agents_out():
    sm = setup_map(cfg.brain_path, list(DEPTS.keys()))
    return [
        {
            "id": a.id, "department": a.department, "lead": a.lead, "name": a.name,
            "role": a.role, "does": a.does, "tools": a.tools, "model": a.model, "effort": a.effort,
            "setUp": sm.get(a.department, False),
        }
        for a in agents_list()
    ]


# ---------- static frontend ----------

@app.get("/", response_class=HTMLResponse)
@app.get("/command-centre-v2.html", response_class=HTMLResponse)
async def root():
    return FileResponse(HTML) if HTML.exists() else HTMLResponse("<h1>build the frontend first: npm run build</h1>", 500)


@app.get("/dark", response_class=HTMLResponse)
async def dark():
    if not HTML.exists():
        return HTMLResponse("<h1>build the frontend first: npm run build</h1>", 500)
    text = HTML.read_text()
    return HTMLResponse(text.replace("<body>", '<body class="dark">', 1))


# ---------- read-only info ----------

@app.get("/api/health")
async def health():
    rl = routines_mod.load(cfg.brain_path, agents_list())
    return {
        "ok": True, "version": VERSION, "backend": "langgraph", "model": cfg.model,
        "modelName": MODELS[cfg.model].name if cfg.model in MODELS else cfg.model,
        "models": MODEL_KEYS, "effort": None, "efforts": EFFORT_KEYS,
        "name": cfg.name, "brain": str(cfg.brain_path), "notes": brain_summary(cfg.brain_path)["notes"],
        "depts": list(DEPTS.keys()), "agents": len(agents_list()),
        "setup": setup_map(cfg.brain_path, list(DEPTS.keys())),
        "routines": {"count": len(rl["routines"]), "paused": sum(1 for r in rl["routines"] if r["paused"]), "depts": routines_mod.ALLOWED},
        "roster": {"customised": _roster_cache["customised"], "briefed": _roster_cache["briefed"],
                   "files": _roster_cache["files"], "problems": _roster_cache["problems"]},
        "skills": refresh_skills().summary(),
        "tools": {"web": cfg.tools.get("web", True)},
        "mcp": mcp_registry.summary(),
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
    return {"dir": str(cfg.brain_path / "Agents Office" / "feedback"), "agents": out}


@app.get("/api/mcp")
async def get_mcp(refresh: int = 0):
    if refresh:
        await mcp_registry.discover()
    return {**mcp_registry.summary(), "tools": True}


@app.get("/api/brain")
async def get_brain():
    return brain_summary(cfg.brain_path)


@app.get("/api/usage")
async def get_usage(refresh: int = 0):
    from . import usage as usagemod
    data_dir = ROOT / "data"
    if refresh:
        r = await usagemod.fetch_usage()
        if r.get("ok"):
            return r
    st = usagemod.load_state(data_dir)
    return usagemod.fallback(st)


# ---------- tasks ----------

@app.get("/api/tasks")
async def list_tasks():
    return await db.list_tasks()


@app.post("/api/tasks")
async def create_task(req: Request):
    body = await req.json()
    dept = body.get("dept")
    text = str(body.get("text") or "").strip()
    if dept not in DEPTS or not text:
        return JSONResponse({"error": "dept and text are required"}, status_code=400)
    routed = await engine.route(dept, text, agents_list())
    task = {
        "id": db.nid(), "dept": dept, "text": text, "by": "you", "state": "next",
        "agent": routed["agent"], "title": routed["title"], "plan": routed["plan"],
        "eta_minutes": routed["eta_minutes"], "why": routed["why"], "needsOk": routed["needs_ok"],
        "createdAt": time.time() * 1000,
    }
    if body.get("model"):
        task["model"] = body["model"]
    if body.get("effort"):
        task["effort"] = body["effort"]
    await db.save_task(task)
    return task


async def _execute(task: dict, feedback: str | None, mode: str | None) -> dict:
    agent = find_agent(task["agent"])
    out = await engine.run_task(task, feedback, mode, agent, agents_list(), refresh_skills(), cfg.brain_path, cfg.model, None)
    return out


@app.post("/api/tasks/{task_id}/run")
@app.post("/api/tasks/{task_id}/revise")
async def run_or_revise_task(task_id: str, req: Request):
    body = {}
    try:
        body = await req.json()
    except Exception:
        pass
    feedback = body.get("feedback")
    task = await db.get_task(task_id)
    if not task:
        return JSONResponse({"error": "not found"}, status_code=404)
    task["state"] = "doing"
    await db.save_task(task)
    async with _run_lock:
        try:
            out = await _execute(task, feedback, None)
            task.update(result=out["result"], state="done", skills=out["skills"],
                        modelUsed=out["modelUsed"], modelFrom=out["modelFrom"],
                        effortUsed=out["effortUsed"], effortFrom=out["effortFrom"])
        except Exception as e:
            task.update(state="done", error=True, result=str(e))
    await db.save_task(task)
    if feedback:
        verdict = await learn.classify(lambda s, u: engine.ask(s, u), find_agent(task["agent"]), task, feedback)
        learn.record(cfg.brain_path, find_agent(task["agent"]), task, feedback, verdict)
    return task


@app.post("/api/tasks/{task_id}/approve")
@app.post("/api/tasks/{task_id}/reject")
async def approve_or_reject_task(task_id: str, req: Request):
    path = req.url.path
    is_approve = path.endswith("/approve")
    task = await db.get_task(task_id)
    if not task or task.get("state") != "waiting":
        return JSONResponse({"error": "task is not waiting for approval"}, status_code=400)
    body = {}
    try:
        body = await req.json()
    except Exception:
        pass
    feedback = body.get("feedback") if not is_approve else None
    task["state"] = "doing"
    await db.save_task(task)

    async def _bg():
        async with _run_lock:
            t = await db.get_task(task_id)
            try:
                mode = "approve" if is_approve else "draft"
                out = await _execute(t, feedback, mode)
                if is_approve:
                    t["result"] = (t.get("result") or "") + "\n\n" + out["result"]
                    t["state"] = "done"
                    t["approvedAt"] = time.time() * 1000
                else:
                    t["draft"] = out["result"]
                    t["state"] = "waiting"
                    t["ask"] = routines_mod.ask_line(t)
            except Exception as e:
                t["state"] = "done"
                t["error"] = True
                t["result"] = str(e)
            await db.save_task(t)
        if feedback:
            verdict = await learn.classify(lambda s, u: engine.ask(s, u), find_agent(t["agent"]), t, feedback)
            learn.record(cfg.brain_path, find_agent(t["agent"]), t, feedback, verdict)

    asyncio.create_task(_bg())
    return {"ok": True, "id": task_id, "state": "doing"}


@app.delete("/api/tasks/{task_id}")
async def delete_task(task_id: str):
    await db.delete_task(task_id)
    return {"ok": True}


# ---------- routines ----------

def _routines_out():
    rl = routines_mod.load(cfg.brain_path, agents_list())
    return {"routines": rl["routines"], "depts": routines_mod.ALLOWED, "path": str(rl["path"]), "problems": rl["problems"]}


@app.get("/api/routines")
async def get_routines():
    return _routines_out()


@app.post("/api/routines")
async def create_routine(req: Request):
    body = await req.json()
    dept = body.get("dept")
    if dept not in DEPTS or dept == "brain":
        return JSONResponse({"error": "unknown department"}, status_code=400)
    if dept not in routines_mod.ALLOWED:
        return JSONResponse({"error": routines_mod.refusal(dept)}, status_code=400)
    text = str(body.get("text") or "").strip()
    if not text:
        return JSONResponse({"error": "no task text"}, status_code=400)
    when = body.get("when")
    if not when:
        parsed = whenmod.parse_when(text)
        when = parsed["when"] if parsed else None
    if not whenmod.valid(when):
        return JSONResponse({"error": "could not work out a schedule — include a day/time"}, status_code=400)
    agent_id = body.get("agent")
    if not agent_id:
        routed = await engine.route(dept, text, agents_list())
        agent_id = routed["agent"]
    rl = routines_mod.load(cfg.brain_path, agents_list())
    draft = {"dept": dept, "agent": agent_id, "text": text, "title": body.get("title") or text[:90],
             "when": when, "needsOk": body.get("needsOk", routines_mod.guess_needs_ok(text)), "paused": False}
    if body.get("model"):
        draft["model"] = body["model"]
    if body.get("effort"):
        draft["effort"] = body["effort"]
    v = routines_mod.validate(draft, agents_list(), rl["routines"])
    if v["problems"]:
        return JSONResponse({"error": "; ".join(v["problems"])}, status_code=400)
    routines_mod.save(cfg.brain_path, rl["routines"] + [v["routine"]])
    return {"ok": True, "routine": v["routine"]}


@app.post("/api/routines/{routine_id}/run")
async def run_routine_now(routine_id: str):
    rl = routines_mod.load(cfg.brain_path, agents_list())
    r = next((x for x in rl["routines"] if x["id"] == routine_id), None)
    if not r:
        return JSONResponse({"error": "not found"}, status_code=404)
    await _fire_routine(r, late=False)
    return {"ok": True}


@app.post("/api/routines/{routine_id}/pause")
@app.post("/api/routines/{routine_id}/resume")
async def pause_resume_routine(routine_id: str, req: Request):
    paused = req.url.path.endswith("/pause")
    rl = routines_mod.load(cfg.brain_path, agents_list())
    out = [{**r, "paused": paused} if r["id"] == routine_id else r for r in rl["routines"]]
    routines_mod.save(cfg.brain_path, out)
    return {"ok": True}


@app.post("/api/routines/{routine_id}")
async def patch_routine(routine_id: str, req: Request):
    body = await req.json()
    rl = routines_mod.load(cfg.brain_path, agents_list())
    out = []
    found = False
    for r in rl["routines"]:
        if r["id"] == routine_id:
            found = True
            patch = {k: v for k, v in body.items() if k in ("needsOk", "paused", "text", "title", "when", "model", "effort")}
            out.append({**r, **patch})
        else:
            out.append(r)
    if not found:
        return JSONResponse({"error": "not found"}, status_code=404)
    routines_mod.save(cfg.brain_path, out)
    return {"ok": True}


@app.delete("/api/routines/{routine_id}")
async def delete_routine(routine_id: str):
    rl = routines_mod.load(cfg.brain_path, agents_list())
    routines_mod.save(cfg.brain_path, [r for r in rl["routines"] if r["id"] != routine_id])
    return {"ok": True}


async def _fire_routine(r: dict, late: bool):
    st = await db.load_routine_state()
    task = {
        "id": db.nid(), "dept": r["dept"], "agent": r["agent"], "text": r["text"], "title": r["title"],
        "plan": r.get("plan", []), "by": "routine", "state": "next", "routine": r["id"],
        "when": r["when"], "due": time.time() * 1000, "late": late, "needsOk": r["needsOk"],
        "routineModel": r.get("model"), "routineEffort": r.get("effort"), "createdAt": time.time() * 1000,
    }
    await db.save_task(task)
    routines_mod.advance(st, r, task_id=task["id"], late=late)
    await db.save_routine_state(st)
    asyncio.create_task(_run_server_task(task["id"]))


async def _run_server_task(task_id: str):
    async with _run_lock:
        task = await db.get_task(task_id)
        if not task:
            return
        task["state"] = "doing"
        await db.save_task(task)
        try:
            mode = "routine" if not task.get("needsOk") else "draft"
            out = await _execute(task, None, mode)
            if task.get("needsOk"):
                task["draft"] = out["result"]
                task["state"] = "waiting"
                task["ask"] = routines_mod.ask_line(task)
            else:
                task["result"] = out["result"]
                task["state"] = "done"
        except Exception as e:
            task["state"] = "done"
            task["error"] = True
            task["result"] = str(e)
        await db.save_task(task)


async def _tick_routines():
    while True:
        try:
            rl = routines_mod.load(cfg.brain_path, agents_list())
            st = await db.load_routine_state()
            merged = routines_mod.with_state(rl["routines"], st)
            if merged["changed"]:
                await db.save_routine_state(st)
            for hit in routines_mod.due(rl["routines"], st):
                await _fire_routine(hit["routine"], hit["late"])
        except Exception:
            pass
        await asyncio.sleep(20)


@app.on_event("startup")
async def startup():
    await db.get_pool()
    asyncio.create_task(_tick_routines())


# ---------- chat ----------

@app.post("/api/chat")
async def chat(req: Request):
    body = await req.json()
    agent_id = body.get("agent")
    text = str(body.get("text") or "").strip()
    history = body.get("history") or []
    agent = find_agent(agent_id)
    if not agent:
        return JSONResponse({"error": "unknown agent"}, status_code=400)

    if not onboard_active(ROOT / "data", agent.department):
        rl = routines_mod.load(cfg.brain_path, agents_list())
        lower = text.lower()
        if any(k in lower for k in ("routine", "schedule", "timetable")):
            return {"reply": routines_mod.list_text(rl["routines"], agent.department, agents_list())}
        for verb, fn in (("pause", "pause"), ("resume", "resume"), ("delete", "delete"), ("run", "run")):
            if lower.startswith(verb):
                m = routines_mod.match_routine(rl["routines"], agent.department, lower[len(verb):])
                if m:
                    if verb == "delete":
                        routines_mod.save(cfg.brain_path, [r for r in rl["routines"] if r["id"] != m["id"]])
                    elif verb in ("pause", "resume"):
                        routines_mod.save(cfg.brain_path, [{**r, "paused": verb == "pause"} if r["id"] == m["id"] else r for r in rl["routines"]])
                    elif verb == "run":
                        await _fire_routine(m, late=False)
                    return {"reply": f'Done — "{m["title"]}" {verb}d.'}

    reply = await engine.chat(agent, text, history, agents_list(), refresh_skills(), cfg.brain_path, cfg.model, None)
    return {"reply": reply}


@app.exception_handler(Exception)
async def on_error(_req, exc: Exception):
    return JSONResponse({"error": str(exc)}, status_code=500)
