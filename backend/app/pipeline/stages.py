"""The work done in each stage. Each function returns a dict merged into the graph
state and writes its findings as evidence rows (ids are stable per job/stage/attempt,
so a node that re-runs after an interrupt updates rows instead of duplicating them).

Models: research/drafts/tests run on the cheap pinned roles; the builder is pinned to
its own role. Every model call is metered by the node wrapper in graph.py."""
from __future__ import annotations

import json
import time
from pathlib import Path

from .. import db
from ..config import load_config
from ..context import build_pack, fence
from ..context import seat as seat_of
from ..policy import redact_secrets
from . import activity
from . import exposure as exp
from .ports import get_deps


def _eid(job_id: str, stage: str, attempt: int, n: str) -> str:
    return f"{job_id}:{stage}:{attempt}:{n}"


async def _evidence(state: dict, stage: str, kind: str, title: str, ok: bool | None, body: dict, n: str) -> str:
    attempt = int(state.get("loops", {}).get(stage, 0))
    return await db.add_evidence(state["job_id"], stage, kind, title, ok, {**body, "attempt": attempt},
                                 evidence_id=_eid(state["job_id"], stage, attempt, n))


def _seats(stage: str) -> list[str]:
    cfg = load_config()
    if not cfg.pipeline.get("seats_enabled"):
        return []
    for s in cfg.pipeline.get("stages", []):
        if s["name"] == stage:
            return list(s.get("seats") or []) if exp.is_live(cfg, s["dept"]) else []
    return []


SEAT_JSON = ('Reply with JSON only: {"finding":"2-4 sentences","risks":["..."],"confidence":"low|medium|high"}. '
             "You give information for the lead to weigh; you do not approve or reject anything.")


async def run_seats(state: dict, stage: str, tasks: dict[str, str], *, role: str = "research") -> str:
    """Run the stage's seat workers in parallel. Each returns a finding (evidence kind \"finding\", ok=None:
    information, never a verdict). A seat that fails writes a note instead of failing the stage.
    Returns the findings as text for the lead's own step."""
    import asyncio
    deps = get_deps()
    wanted = [s for s in _seats(stage) if s in tasks]
    brief = fence(json.dumps(state["brief"])[:4000])
    evidence = await db.list_evidence(state["job_id"])

    job = await db.get_job(state["job_id"]) or {"id": state["job_id"]}

    async def one(sid: str) -> tuple[str, dict]:
        shown = await activity.start(job, stage, sid, tasks[sid][:80], dept=activity.stage_cfg(stage).get("dept"), key="seat")
        try:
            system = await build_pack(sid, stage=stage, query=f'{state["brief"].get("title", "")} {tasks[sid]}', evidence=evidence)
            data = await deps.chat_json(system + "\n\n" + SEAT_JSON, f"Your task: {tasks[sid]}\n\nBrief:\n{brief}", role=role)
            res = {"finding": str(data.get("finding", ""))[:1200], "risks": [str(r)[:200] for r in data.get("risks", [])][:5],
                   "confidence": str(data.get("confidence", ""))[:10]}
            await activity.finish(shown, result=res["finding"])
            return sid, res
        except Exception as exc:  # a seat that cannot answer must not stop the stage
            await activity.finish(shown, ok=False, result=f"could not answer: {type(exc).__name__}")
            return sid, {"finding": "", "risks": [], "error": type(exc).__name__}

    out = await asyncio.gather(*(one(s) for s in wanted))
    lines = []
    for sid, d in out:
        seat_ = seat_of(sid)
        await _evidence(state, stage, "finding", f"{seat_.name if seat_ else sid}: finding", None, {**d, "seat": sid}, f"seat-{sid}")
        if d.get("finding"):
            lines.append(f"- {sid}: {d['finding']} Risks: {'; '.join(d['risks']) or 'none stated'}")
    return "\n".join(lines)


def _lead(state: dict, stage: str) -> str:
    """The stage lead's seat id, or "" when its department is offline (no persona is used then)."""
    cfg = load_config()
    for s in cfg.pipeline.get("stages", []):
        if s["name"] == stage:
            return s["lead"] if exp.is_live(cfg, s["dept"]) else ""
    return ""


async def _lead_pack(state: dict, stage: str, query: str) -> str:
    lead = _lead(state, stage)
    return (await build_pack(lead, stage=stage, query=query) + "\n\n") if lead else ""


def _feedback(state: dict) -> str:
    fb = state.get("feedback")
    return f"\n\nThe reviewer sent this back with these problems, fix them: {fb}" if fb else ""


async def intake(state: dict) -> dict:
    """Deterministic: the brief must be complete before any model spends a token."""
    b = state["brief"]
    problems = []
    if not str(b.get("title", "")).strip():
        problems.append("no title")
    if len(str(b.get("description", "")).strip()) < 20:
        problems.append("description is too short to scope")
    if state["kind"] == "client" and not str(b.get("deposit_ref", "")).strip():
        problems.append("client work needs a deposit or contract reference before anything is built")
    await _evidence(state, "intake", "check", "brief is complete", not problems, {"problems": problems}, "brief")
    return {"feedback": "; ".join(problems) if problems else ""}


async def verify(state: dict) -> dict:
    b = state["brief"]
    system = ("You verify whether a client job is worth taking. Reply with JSON only: "
              '{"deposit_real":bool,"scope_clear":bool,"price_fits_effort":bool,"deadline_realistic":bool,'
              '"repeatable":bool,"risks":["..."],"summary":"..."}. Base every answer only on the brief; '
              "if the brief does not say, answer false and name it under risks.")
    found = await run_seats(state, "verify", {
        "scout": "Name the competitors or substitutes this client could use instead, and what is publicly known about demand. Say what you cannot know from the brief.",
        "ilm": "Judge how well this request fits a small web-app MVP client we want: clarity, budget signals, red flags.",
        "enzo": "Judge whether the stated price fits the effort and what the margin risk is."})
    from .jobs import lane_hours
    user = (f"Brief:\n{fence(json.dumps(b)[:4000])}\nDelivery target: a working preview within "
            f"{lane_hours(load_config(), state.get('lane', 'build')):g} hours, built from our standard web-app template."
            + (f"\n\nSpecialist findings:\n{found}" if found else "") + _feedback(state))
    system = await _lead_pack(state, "verify", json.dumps(b)[:300]) + system
    data = await get_deps().chat_json(system, user, role="research")
    checks = {k: bool(data.get(k)) for k in ("deposit_real", "scope_clear", "price_fits_effort", "deadline_realistic")}
    ok = all(checks.values())
    await _evidence(state, "verify", "memo", "client job verification", ok,
                    {**checks, "repeatable": bool(data.get("repeatable")), "risks": data.get("risks", []),
                     "summary": str(data.get("summary", ""))[:1500]}, "memo")
    return {}


async def scope(state: dict) -> dict:
    b = state["brief"]
    system = ("You scope a small web app MVP that will be built on our fixed template (Next.js App Router + TypeScript, "
              "Drizzle on Postgres, Better Auth email/password, Vitest, Playwright); do not propose another stack. "
              "Keep it to what one builder can finish in a few hours. Reply with JSON only: "
              '{"acceptance_criteria":["testable statement",...],"tasks":["..."],"stack":"...","estimate_hours":number,'
              '"out_of_scope":["..."]}. Criteria must be checkable by an automated test.')
    found = await run_seats(state, "scope", {
        "pco": "List the technical risks and unknowns in building this brief as a small JS/TS web app, and what you would do first."}, role="drafts")
    user = f"Brief:\n{fence(json.dumps(b)[:4000])}" + (f"\n\nSpecialist findings:\n{found}" if found else "") + _feedback(state)
    system = await _lead_pack(state, "scope", json.dumps(b)[:300]) + system
    data = await get_deps().chat_json(system, user, role="drafts")
    crit = [str(c) for c in data.get("acceptance_criteria", [])][:12]
    ok = len(crit) >= 1
    await _evidence(state, "scope", "memo", "scope and acceptance criteria", ok,
                    {"acceptance_criteria": crit, "tasks": data.get("tasks", []), "stack": data.get("stack"),
                     "estimate_hours": data.get("estimate_hours"), "out_of_scope": data.get("out_of_scope", [])}, "scope")
    return {"scope": {"acceptance_criteria": crit, "tasks": data.get("tasks", []), "stack": data.get("stack")}}


async def build(state: dict) -> dict:
    deps = get_deps()
    cfg = load_config()
    job_dir = Path(cfg.sandbox["jobs_dir"]) / state["job_id"]
    job_dir.mkdir(parents=True, exist_ok=True)
    brief = {**state["brief"], "scope": state.get("scope", {}), "feedback": state.get("feedback", "")}
    limits = {"minutes": cfg.worker.get("timeout_minutes", 180), "model": cfg.roles.get("builder"),
              "max_turns": cfg.worker.get("max_turns", 250)}
    res = await deps.worker.run(job_dir, brief, limits)
    pinned = cfg.roles.get("builder", "")
    from ..llm import same_model
    swapped = [m for m in res.get("models_seen", []) if not same_model(pinned, m)]
    ok = res.get("exit_state") == "ok" and bool(res.get("patch_path")) and not swapped
    checks = res.get("checks")
    if checks is None:  # a worker that cannot prove the app runs does not pass the build
        checks = [{"name": "the app was installed, built, tested and started", "ok": False,
                   "detail": "this worker reports no check results"}]
    for i, c in enumerate(checks[:12]):
        await _evidence(state, "build", "check", c["name"], bool(c.get("ok")),
                        {"detail": redact_secrets(str(c.get("detail", "")))[-2500:], "ms": int(c.get("ms") or 0)}, f"run{i}")
    await _evidence(state, "build", "patch", "build result", ok,
                    {"exit_state": res.get("exit_state"), "patch_path": res.get("patch_path"),
                     "log_path": res.get("log_path"), "tokens": res.get("tokens", 0), "usd": res.get("usd", 0.0),
                     "models_seen": res.get("models_seen", []), "model_swapped": swapped}, "patch")
    return {"patch": {"path": res.get("patch_path"), "log": res.get("log_path")},
            "_cost": {"tokens": int(res.get("tokens", 0)), "usd": worker_usd(pinned, res)}}


def worker_usd(model: str, res: dict) -> float:
    """The build's cost from its token counts and the price table, so the cap means the same
    thing for every worker. Cache reads are priced at a tenth of input. Only a worker that
    reports no split falls back to its own USD figure."""
    from ..llm import price
    if "tokens_in" in res or "tokens_out" in res:
        return price(model, int(res.get("tokens_in", 0)), int(res.get("tokens_out", 0))) + \
            round(price(model, int(res.get("tokens_cached", 0))) * 0.1, 6)
    return float(res.get("usd", 0.0))


def _check_owner(name: str) -> str:
    """Which security seat owns a deterministic check (attribution only; the check decides, not the seat)."""
    n = name.lower()
    seats = _seats("security")
    pick = "kmail" if "secret" in n else "vmail" if any(w in n for w in ("depend", "audit", "licen", "package")) else "recon"
    return pick if pick in seats else (seats[0] if seats else "")


async def security(state: dict) -> dict:
    patch = (state.get("patch") or {}).get("path")
    if not patch:
        await _evidence(state, "security", "check", "patch is available", False, {"detail": "no patch to scan"}, "nopatch")
        return {}
    for i, r in enumerate(await get_deps().checks.scan(patch)):
        await _evidence(state, "security", "check", r["name"], bool(r["ok"]),
                        {"detail": redact_secrets(str(r.get("detail", ""))), "seat": _check_owner(r["name"])}, f"c{i}")
    return {}


async def preview(state: dict) -> dict:
    job = await db.get_job(state["job_id"])
    patch = (state.get("patch") or {}).get("path")
    deployer = get_deps().deployer
    info = await deployer.deploy_preview(job, patch)
    ttl = int(load_config().exposure.get("preview_ttl_days", 7))
    prev = {"app_id": info.get("app_id"), "internal_url": info.get("internal_url"), "url": None, "tier": 0,
            "expiresAt": db.now_ms() + ttl * 86400 * 1000}
    await _evidence(state, "preview", "check", "preview deployed privately (Tier 0)", bool(info.get("app_id")),
                    {"app_id": info.get("app_id"), "internal_url": info.get("internal_url"), "public": False,
                     "seat": "dash" if "dash" in _seats("preview") else ""}, "deploy")
    from . import jobs
    await jobs.touch(state["job_id"], preview=prev, tier=0)
    return {"preview": prev}


async def exposure(state: dict) -> dict:
    """Evidence for the exposure decision. Tier 0 needs none. A gated preview needs proof
    that the authentication layer is configured and that every security check passed; the
    unauthenticated-request probe can only run once the route exists, so it runs right
    after apply_exposure and rolls the app back if it fails."""
    tier = int(state.get("requested_tier", 0))
    if tier <= 0:
        await _evidence(state, "exposure", "check", "stays private (Tier 0)", True, {"tier": 0}, "private")
        return {}
    prev = state.get("preview") or {}
    auth = await get_deps().deployer.auth_configured(prev)
    await _evidence(state, "exposure", "check", "authentication layer is configured on the app", bool(auth.get("ok")),
                    {"detail": str(auth.get("detail", ""))[:500]}, "authcfg")
    sec = [e for e in await db.list_evidence(state["job_id"]) if e["stage"] == "security"
           and e["body"].get("attempt") == int(state.get("loops", {}).get("security", 0))]
    await _evidence(state, "exposure", "check", "all security checks passed", bool(sec) and all(e.get("ok") for e in sec),
                    {"checks": [e["title"] for e in sec]}, "secsummary")
    return {}


async def handoff(state: dict) -> dict:
    job = await db.get_job(state["job_id"])
    prev = state.get("preview") or {}
    system = ("Write the client handoff memo for a finished MVP preview as JSON only: "
              '{"summary":"...","how_to_open":"...","what_was_built":["..."],"known_limits":["..."],"next_steps":["..."]}. '
              "Do not invent URLs or credentials; the owner adds those. Plain language for a non-technical client.")
    found = await run_seats(state, "handoff", {
        "piper": "State what the client was promised, the price and terms position, and the next commercial step for the owner.",
        "cmail": "Write 3 plain-language sentences telling a non-technical client what they will receive."}, role="drafts")
    system = await _lead_pack(state, "handoff", json.dumps(state["brief"])[:300]) + system
    user = (f"Brief:\n{fence(json.dumps(state['brief'])[:3000])}\nScope:\n{json.dumps(state.get('scope', {}))[:2000]}\n"
            f"Preview tier: {prev.get('tier', 0)}; expires: {prev.get('expiresAt')}." + (f"\n\nSpecialist findings:\n{found}" if found else "")) + _feedback(state)
    data = await get_deps().chat_json(system, user, role="drafts")
    memo = {k: data.get(k) for k in ("summary", "how_to_open", "what_was_built", "known_limits", "next_steps")}
    await _evidence(state, "handoff", "memo", "client handoff memo", bool(memo.get("summary")), memo, "memo")
    return {}


async def research(state: dict) -> dict:
    from .research import research as run
    return await run(state)


WORK = {"intake": intake, "verify": verify, "scope": scope, "build": build, "security": security,
        "preview": preview, "exposure": exposure, "handoff": handoff, "research": research}
