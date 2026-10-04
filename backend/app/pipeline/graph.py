"""The pipeline graph.

    intake -> [verify -> scope -> build -> security -> preview -> exposure] -> apply_exposure -> handoff -> finish

Every stage S after intake is three nodes:
    S         work: agents produce evidence (metered, budget-capped)
    S_review  the stage owner's lead reviews the evidence and records PASS/FAIL
    S_gate    waits until every required role has a PASS; a FAIL sends the stage back
              with the reasons (at most max_review_loops times), then parks the job

Waiting uses LangGraph's interrupt(). A node re-runs from its first line when resumed,
so S_gate computes everything from the database first and only then may interrupt;
nothing before that line has side effects. Approvals are rows keyed by
(job, stage, role), so recording one twice changes nothing.
"""
from __future__ import annotations

import logging

from langgraph.checkpoint.base import BaseCheckpointSaver
from langgraph.graph import END, StateGraph
from langgraph.types import interrupt
from typing_extensions import TypedDict

from .. import db
from ..config import load_config
from ..llm import BudgetExceeded, RunMeter, current_meter
from . import exposure as exp
from . import jobs, leads
from .stages import WORK

log = logging.getLogger("agents_office.pipeline")

ORDER = ["verify", "scope", "build", "security", "preview", "exposure"]
NEXT = {"verify": "scope", "scope": "build", "build": "security", "security": "preview",
        "preview": "exposure", "exposure": "apply_exposure"}


class JobState(TypedDict, total=False):
    job_id: str
    kind: str
    lane: str
    brief: dict
    requested_tier: int
    scope: dict
    patch: dict
    preview: dict
    feedback: str
    loops: dict
    route: str
    park_stage: str
    park_reason: str


# ---------- node factories ----------

def _work_node(stage: str):
    async def node(state: JobState) -> dict:
        jid = state["job_id"]
        if await jobs.is_killed(jid):
            return {"route": "kill"}
        await jobs.set_stage(jid, stage, "working")
        job = await db.get_job(jid)
        usd_cap, token_cap = jobs.lane_budget(load_config(), job.get("lane", "build"))
        if token_cap and job["costs"]["tokens"] >= token_cap:
            return await _park(jid, stage, f'budget: {job["costs"]["tokens"]} tokens used, at the {token_cap} token cap')
        meter = RunMeter(label=f"job:{jid}:{stage}", usd_cap=max(0.0, usd_cap - job["costs"]["usd"]))
        tok = current_meter.set(meter)
        out: dict = {}
        try:
            out = await WORK[stage](state)
        except BudgetExceeded as exc:
            return await _park(jid, stage, f"budget: {exc}")
        except Exception as exc:
            log.exception("job %s stage %s failed", jid, stage)
            if router_down(exc):
                return await _park(jid, stage, "the model router (9router) is unreachable; start it and retry this stage")
            return await _park(jid, stage, f"{stage} failed: {type(exc).__name__}")
        finally:
            current_meter.reset(tok)
            extra = out.pop("_cost", None) if isinstance(out, dict) else None
            await jobs.add_cost(jid, meter.tokens + (extra or {}).get("tokens", 0), meter.usd + (extra or {}).get("usd", 0.0))
        costs = (await db.get_job(jid))["costs"]
        if costs["usd"] > usd_cap:  # includes the build worker's tokens, priced from the table
            return await _park(jid, stage, f'budget: ${costs["usd"]:.2f} spent, over the ${usd_cap:.2f} cap')
        if token_cap and costs["tokens"] > token_cap:
            return await _park(jid, stage, f'budget: {costs["tokens"]} tokens used, over the {token_cap} token cap')
        await jobs.set_stage(jid, stage, "review")
        return {**out, "route": ""}
    return node


_ROUTER_DOWN = {"APIConnectionError", "APITimeoutError", "ConnectError", "ConnectTimeout", "ReadTimeout"}


def router_down(exc: BaseException) -> bool:
    """True when the error (or anything it was raised from) is a connection failure to the router."""
    seen = 0
    while exc is not None and seen < 6:
        if type(exc).__name__ in _ROUTER_DOWN:
            return True
        exc, seen = exc.__cause__ or exc.__context__, seen + 1
    return False


async def _park(jid: str, stage: str, reason: str) -> dict:
    await jobs.touch(jid, status="parked", parkReason=reason)
    await jobs.set_stage(jid, stage, "failed", reason=reason[:300])
    await jobs.event(jid, f"parked at {stage}: {reason}")
    return {"route": "park", "park_stage": stage, "park_reason": reason}


def _review_node(stage: str):
    async def node(state: JobState) -> dict:
        jid = state["job_id"]
        if state.get("route") in ("park", "kill"):
            return {}
        cfg = load_config()
        job = await db.get_job(jid)
        tier = int(state.get("requested_tier", 0))
        clicks = await db.counter("tier1_owner_clicks")
        roles = [r for r in exp.stage_roles(cfg, stage, tier=tier, owner_clicks=clicks) if r != exp.OWNER]
        existing = {a["role"] for a in await db.list_approvals(jid) if a["stage"] == stage}
        evidence = await db.list_evidence(jid)
        attempt = int(state.get("loops", {}).get(stage, 0))
        evidence = [e for e in evidence if e["stage"] != stage or e["body"].get("attempt") == attempt]
        for role in roles:
            if role in existing:
                continue
            try:
                out = await leads.review(stage, role, role, job, evidence)
            except Exception as exc:
                if router_down(exc):
                    return await _park(jid, stage, "the model router (9router) is unreachable; start it and retry this stage")
                raise
            c = out.get("cost") or {}
            if c.get("tokens") or c.get("usd"):
                await jobs.add_cost(jid, int(c.get("tokens", 0)), float(c.get("usd", 0.0)))
            await db.record_approval(jid, stage, role, out["verdict"], "; ".join(out["reasons"]), out["cites"], role)
            await jobs.event(jid, f'{role} {out["verdict"]} on {stage}')
        return {}
    return node


def _gate_node(stage: str):
    async def decide(state: JobState) -> dict:
        jid = state["job_id"]
        cfg = load_config()
        if await jobs.is_killed(jid):
            return {"route": "kill"}
        approvals = [a for a in await db.list_approvals(jid) if a["stage"] == stage]
        fails = [a for a in approvals if a["verdict"] == "FAIL"]
        if fails:
            loops = dict(state.get("loops") or {})
            loops[stage] = loops.get(stage, 0) + 1
            notes = "; ".join(f'{a["role"]}: {a["note"]}' for a in fails)[:3000]
            await db.clear_approvals(jid, stage)
            if loops[stage] > int(cfg.pipeline.get("max_review_loops", 2)):
                return {**await _park(jid, stage, f"{stage} failed review {loops[stage]} times: {notes}"), "loops": loops}
            await jobs.set_stage(jid, stage, "failed", reason=notes[:300])
            await jobs.event(jid, f"{stage} sent back: {notes[:200]}")
            return {"route": "retry", "feedback": notes, "loops": loops}
        tier = int(state.get("requested_tier", 0))
        clicks = await db.counter("tier1_owner_clicks")
        required = exp.stage_roles(cfg, stage, tier=tier, owner_clicks=clicks)
        passed = {a["role"] for a in approvals if a["verdict"] == "PASS"}
        missing = [r for r in required if r not in passed]
        if missing:
            await jobs.touch(jid, status="waiting",
                             pending=[{"stage": stage, "roles": missing, "needsOwner": exp.OWNER in missing}])
            await jobs.set_stage(jid, stage, "waiting")
            return {"route": "wait", "missing": missing}
        await jobs.touch(jid, status="running", pending=[])
        await jobs.set_stage(jid, stage, "approved")
        return {"route": "pass", "feedback": ""}

    async def node(state: JobState) -> dict:
        if state.get("route") in ("park", "kill"):
            return {}
        out = await decide(state)
        if out.get("route") == "wait":
            interrupt({"kind": "gate", "stage": stage, "missing": out.get("missing", []), "job": state["job_id"]})
        return {k: v for k, v in out.items() if k != "missing"}
    return node


async def _apply_exposure(state: JobState) -> dict:
    """Runs only after every key for the requested tier is recorded. Adds the public
    route with auth, then immediately probes it without credentials; if access is not
    refused the app is stopped, the preview is withdrawn, and the job parks at "preview"."""
    jid = state["job_id"]
    if state.get("route") in ("park", "kill") or await jobs.is_killed(jid):
        return {"route": "kill"} if await jobs.is_killed(jid) else {}
    tier = int(state.get("requested_tier", 0))
    prev = dict(state.get("preview") or {})
    if tier <= 0 or prev.get("tier") == tier:
        return {}
    from .ports import get_deps
    from .stages import _evidence
    dep = get_deps().deployer
    job = await db.get_job(jid)
    res = await dep.apply_exposure(job, prev, tier)
    prev.update(url=res.get("url"), tier=tier)
    probe = await dep.probe_unauthenticated(prev)
    await _evidence(state, "exposure", "probe", "request without credentials is refused", bool(probe.get("ok")),
                    {"status": probe.get("status"), "url": prev.get("url")}, "authprobe")
    if not probe.get("ok"):
        await dep.stop(job, prev)
        withdrawn = {**prev, "url": None, "tier": 0, "stopped": True}
        await jobs.touch(jid, preview=withdrawn, tier=0)
        return {**await _park(jid, "preview", "the public route answered without credentials; the app was taken down"),
                "preview": withdrawn}
    await jobs.touch(jid, preview=prev, tier=tier)
    await jobs.event(jid, f"exposed at tier {tier}")
    return {"preview": prev}


async def _park_node(state: JobState) -> dict:
    """The job is parked: the owner decides to retry the stage or kill the job."""
    if await jobs.is_killed(state["job_id"]):
        return {"route": "kill"}
    answer = interrupt({"kind": "parked", "stage": state.get("park_stage"), "reason": state.get("park_reason"),
                        "job": state["job_id"]})
    answer = answer if isinstance(answer, dict) else {}
    if answer.get("action") == "retry":
        loops = dict(state.get("loops") or {})
        loops[state["park_stage"]] = 0
        await jobs.touch(state["job_id"], status="running", parkReason=None)
        await db.clear_approvals(state["job_id"], state["park_stage"])
        return {"route": "resume", "loops": loops, "feedback": str(answer.get("note") or "")}
    await jobs.touch(state["job_id"], status="killed")
    return {"route": "kill"}


async def _finish(state: JobState) -> dict:
    if state.get("route") == "kill" or await jobs.is_killed(state["job_id"]):
        return {}
    await jobs.touch(state["job_id"], status="done", pending=[])
    await jobs.event(state["job_id"], "handed off")
    return {}


def _intake_node():
    work = _work_node("intake")

    async def node(state: JobState) -> dict:
        out = await work(state)
        if out.get("route") in ("park", "kill"):
            return out
        ev = [e for e in await db.list_evidence(state["job_id"]) if e["stage"] == "intake"]
        if any(e.get("ok") is False for e in ev):
            return await _park(state["job_id"], "intake", "the brief is incomplete: " + (out.get("feedback") or "see evidence"))
        await jobs.set_stage(state["job_id"], "intake", "approved")
        return {"route": ""}
    return node


# ---------- assembly ----------

def build_graph() -> StateGraph:
    g = StateGraph(JobState)
    g.add_node("intake", _intake_node())
    for s in ORDER + ["handoff"]:
        g.add_node(s, _work_node(s))
        g.add_node(f"{s}_review", _review_node(s))
        g.add_node(f"{s}_gate", _gate_node(s))
        g.add_edge(s, f"{s}_review")
        g.add_edge(f"{s}_review", f"{s}_gate")
    g.add_node("apply_exposure", _apply_exposure)
    g.add_node("park", _park_node)
    g.add_node("finish", _finish)
    g.set_entry_point("intake")

    def after_work(state: JobState) -> str:
        return "park" if state.get("route") == "park" else ("finish" if state.get("route") == "kill" else "ok")

    def after_intake(state: JobState) -> str:
        return {"park": "park", "kill": "finish"}.get(state.get("route", ""), "verify")

    g.add_conditional_edges("intake", after_intake, {"park": "park", "finish": "finish", "verify": "verify"})
    for s in ORDER + ["handoff"]:
        nxt = NEXT.get(s, "finish") if s != "handoff" else "finish"

        def router(state: JobState, s=s, nxt=nxt) -> str:
            r = state.get("route", "")
            return {"pass": nxt, "retry": s, "wait": f"{s}_gate", "park": "park", "kill": "finish"}.get(r, "park")
        g.add_conditional_edges(f"{s}_gate", router,
                                {nxt: nxt, s: s, f"{s}_gate": f"{s}_gate", "park": "park", "finish": "finish"} if nxt != "finish"
                                else {"finish": "finish", s: s, f"{s}_gate": f"{s}_gate", "park": "park"})
    # apply_exposure -> handoff
    g.add_conditional_edges("apply_exposure",
                            lambda st: {"kill": "finish", "park": "park"}.get(st.get("route", ""), "handoff"),
                            {"finish": "finish", "park": "park", "handoff": "handoff"})
    g.add_conditional_edges("park", lambda st: {"resume": "resume", "kill": "finish"}.get(st.get("route", ""), "finish"),
                            {"resume": "resume_router", "finish": "finish"})
    g.add_node("resume_router", lambda st: {"route": ""})
    g.add_conditional_edges("resume_router", lambda st: st.get("park_stage") or "verify",
                            {s: s for s in ["intake"] + ORDER + ["handoff"]})
    g.add_edge("finish", END)
    return g


_compiled = None


def compile_pipeline(checkpointer: BaseCheckpointSaver | None = None):
    global _compiled
    _compiled = build_graph().compile(checkpointer=checkpointer)
    return _compiled


def compiled():
    if _compiled is None:
        raise RuntimeError("pipeline graph is not compiled")
    return _compiled
