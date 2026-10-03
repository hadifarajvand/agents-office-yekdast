"""Job records: creation, merging updates, stage bookkeeping. A job is one JSON
document in db.jobs; the LangGraph checkpoint holds the graph's own state."""
from __future__ import annotations

import time

from .. import db
from ..config import load_config

TERMINAL = {"done", "killed", "failed"}


def new_job(kind: str, title: str, brief: dict, requested_tier: int = 0) -> dict:
    cfg = load_config()
    now = db.now_ms()
    stages = {s["name"]: {"state": "pending", "lead": s["lead"], "dept": s["dept"], "label": s.get("label", s["name"]),
                          "attempts": 0} for s in cfg.pipeline["stages"]}
    return {
        "id": db.nid(), "kind": kind, "title": title[:120], "brief": brief, "stage": "intake", "status": "running",
        "stages": stages, "pending": [], "preview": None, "requestedTier": requested_tier, "tier": 0,
        "costs": {"tokens": 0, "usd": 0.0}, "events": [], "createdAt": now,
        "deadlineAt": now + cfg.pipeline.get("deadline_days", 3) * 86400 * 1000,
    }


async def touch(job_id: str, **patch) -> dict:
    job = await db.get_job(job_id)
    if job is None:
        raise KeyError(job_id)
    job.update(patch)
    await db.save_job(job)
    return job


async def event(job_id: str, text: str) -> None:
    job = await db.get_job(job_id)
    if job is None:
        return
    job["events"] = (job.get("events") or [])[-49:] + [{"at": db.now_ms(), "text": text[:300]}]
    await db.save_job(job)


async def set_stage(job_id: str, stage: str, state: str, **extra) -> dict:
    """state: pending | working | review | waiting | approved | failed. Moving to
    "working" counts an attempt."""
    job = await db.get_job(job_id)
    if job is None:
        raise KeyError(job_id)
    st = job["stages"][stage]
    if state == "working":
        st["attempts"] = st.get("attempts", 0) + 1
    st.update(state=state, **extra)
    job["stage"] = stage
    await db.save_job(job)
    return job


async def add_cost(job_id: str, tokens: int, usd: float) -> dict:
    job = await db.get_job(job_id)
    job["costs"] = {"tokens": job["costs"]["tokens"] + tokens, "usd": round(job["costs"]["usd"] + usd, 6)}
    await db.save_job(job)
    return job


async def is_killed(job_id: str) -> bool:
    job = await db.get_job(job_id)
    return job is None or job.get("status") == "killed"


def public(job: dict, approvals: list[dict] | None = None, evidence: list[dict] | None = None) -> dict:
    """The shape the UI reads (GET /api/jobs)."""
    cfg = load_config()
    out = {k: job[k] for k in ("id", "kind", "title", "stage", "status", "pending", "preview", "requestedTier",
                               "tier", "costs", "events", "createdAt", "deadlineAt") if k in job}
    # JSONB does not keep key order, so the order comes from the pipeline config.
    order = [st["name"] for st in cfg.pipeline.get("stages", [])]
    names = [n for n in order if n in job["stages"]] + [n for n in job["stages"] if n not in order]
    out["stages"] = [{"name": n, **job["stages"][n]} for n in names]
    out["brief"] = job.get("brief", {})
    out["parkReason"] = job.get("parkReason")
    out["ownerClicksNeeded"] = int(cfg.exposure.get("tier1_owner_clicks", 3))
    if approvals is not None:
        out["approvals"] = approvals
    if evidence is not None:
        out["evidence"] = evidence
    return out


def minutes_left(job: dict) -> float:
    return (job.get("deadlineAt", 0) - time.time() * 1000) / 60000
