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
from ..policy import redact_secrets
from .ports import get_deps


def _eid(job_id: str, stage: str, attempt: int, n: str) -> str:
    return f"{job_id}:{stage}:{attempt}:{n}"


async def _evidence(state: dict, stage: str, kind: str, title: str, ok: bool | None, body: dict, n: str) -> str:
    attempt = int(state.get("loops", {}).get(stage, 0))
    return await db.add_evidence(state["job_id"], stage, kind, title, ok, {**body, "attempt": attempt},
                                 evidence_id=_eid(state["job_id"], stage, attempt, n))


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
    user = f"Brief:\n{json.dumps(b)[:4000]}\nDeadline: {load_config().pipeline.get('deadline_days', 3)} days." + _feedback(state)
    data = await get_deps().chat_json(system, user, role="research")
    checks = {k: bool(data.get(k)) for k in ("deposit_real", "scope_clear", "price_fits_effort", "deadline_realistic")}
    ok = all(checks.values())
    await _evidence(state, "verify", "memo", "client job verification", ok,
                    {**checks, "repeatable": bool(data.get("repeatable")), "risks": data.get("risks", []),
                     "summary": str(data.get("summary", ""))[:1500]}, "memo")
    return {}


async def scope(state: dict) -> dict:
    b = state["brief"]
    system = ("You scope a small JavaScript/TypeScript web app MVP. Reply with JSON only: "
              '{"acceptance_criteria":["testable statement",...],"tasks":["..."],"stack":"...","estimate_hours":number,'
              '"out_of_scope":["..."]}. Criteria must be checkable by an automated test.')
    user = f"Brief:\n{json.dumps(b)[:4000]}" + _feedback(state)
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
    limits = {"minutes": cfg.worker.get("timeout_minutes", 180), "model": cfg.roles.get("builder")}
    res = await deps.worker.run(job_dir, brief, limits)
    pinned = cfg.roles.get("builder", "")
    from ..llm import same_model
    swapped = [m for m in res.get("models_seen", []) if not same_model(pinned, m)]
    ok = res.get("exit_state") == "ok" and bool(res.get("patch_path")) and not swapped
    await _evidence(state, "build", "patch", "build result", ok,
                    {"exit_state": res.get("exit_state"), "patch_path": res.get("patch_path"),
                     "log_path": res.get("log_path"), "tokens": res.get("tokens", 0), "usd": res.get("usd", 0.0),
                     "models_seen": res.get("models_seen", []), "model_swapped": swapped}, "patch")
    return {"patch": {"path": res.get("patch_path"), "log": res.get("log_path")},
            "_cost": {"tokens": int(res.get("tokens", 0)), "usd": float(res.get("usd", 0.0))}}


async def security(state: dict) -> dict:
    patch = (state.get("patch") or {}).get("path")
    if not patch:
        await _evidence(state, "security", "check", "patch is available", False, {"detail": "no patch to scan"}, "nopatch")
        return {}
    for i, r in enumerate(await get_deps().checks.scan(patch)):
        await _evidence(state, "security", "check", r["name"], bool(r["ok"]), {"detail": redact_secrets(str(r.get("detail", "")))}, f"c{i}")
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
                    {"app_id": info.get("app_id"), "internal_url": info.get("internal_url"), "public": False}, "deploy")
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
    user = (f"Brief:\n{json.dumps(state['brief'])[:3000]}\nScope:\n{json.dumps(state.get('scope', {}))[:2000]}\n"
            f"Preview tier: {prev.get('tier', 0)}; expires: {prev.get('expiresAt')}.") + _feedback(state)
    data = await get_deps().chat_json(system, user, role="drafts")
    memo = {k: data.get(k) for k in ("summary", "how_to_open", "what_was_built", "known_limits", "next_steps")}
    await _evidence(state, "handoff", "memo", "client handoff memo", bool(memo.get("summary")), memo, "memo")
    return {}


WORK = {"intake": intake, "verify": verify, "scope": scope, "build": build, "security": security,
        "preview": preview, "exposure": exposure, "handoff": handoff}
