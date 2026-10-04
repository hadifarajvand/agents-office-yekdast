"""Job records: creation, merging updates, stage bookkeeping. A job is one JSON
document in db.jobs; the LangGraph checkpoint holds the graph's own state."""
from __future__ import annotations

import time

from .. import activity, db
from ..config import load_config

TERMINAL = {"done", "killed", "failed"}


LANES = ("validate", "build")


def lane_stages(cfg, lane: str) -> list[str]:
    lanes = cfg.pipeline.get("lanes") or {}
    return list((lanes.get(lane) or {}).get("stages") or [s["name"] for s in cfg.pipeline["stages"] if s["name"] != "research"])


def lane_budget(cfg, lane: str) -> tuple[float, int]:
    """(usd cap, token cap) for one job of this lane."""
    b = (cfg.budget.get("lanes") or {}).get(lane) or {}
    return float(b.get("usd", cfg.budget.get("usd_per_job", 1.0))), int(b.get("tokens", 0) or 0)


def lane_hours(cfg, lane: str) -> float:
    return float(((cfg.pipeline.get("lanes") or {}).get(lane) or {}).get("hours", 7))


def new_job(kind: str, title: str, brief: dict, requested_tier: int = 0, lane: str = "build") -> dict:
    cfg = load_config()
    now = db.now_ms()
    wanted = lane_stages(cfg, lane)
    live = cfg.pipeline.get("live_departments")
    stages = {s["name"]: {"state": "pending", "lead": s["lead"], "dept": s["dept"], "live": s["dept"] in (live or [s["dept"]]),
                          "label": s.get("label", s["name"]), "attempts": 0}
              for s in cfg.pipeline["stages"] if s["name"] in wanted}
    return {
        "id": db.nid(), "kind": kind, "lane": lane, "title": title[:120], "brief": brief, "stage": "intake", "status": "running",
        "stages": stages, "pending": [], "preview": None, "requestedTier": requested_tier, "tier": 0,
        "costs": {"tokens": 0, "usd": 0.0}, "events": [], "createdAt": now,
        "deadlineAt": now + int(lane_hours(cfg, lane) * 3600 * 1000),
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
    activity.emit("job-event", text, job=job_id, stage=job.get("stage"), connector="postgres")


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
    activity.emit("stage", f'{job.get("title", job_id)[:40]}: {stage} {state}', job=job_id, stage=stage, connector="postgres",
                  level="warn" if state == "failed" else "info")
    return job


async def notify_once(job_id: str, key: str, text: str) -> bool:
    """Tell the owner once per key (graph nodes re-run on resume, so this must be idempotent).
    Never raises: a dead notification channel must not stop a job."""
    from .ports import get_deps
    job = await db.get_job(job_id)
    if job is None or key in (job.get("notified") or []):
        return False
    job["notified"] = (job.get("notified") or [])[-40:] + [key]
    await db.save_job(job)
    try:
        n = getattr(get_deps(), "notifier", None)
        if not n or not getattr(n, "enabled", False):
            return False
        url = load_config().notify.get("office_url", "")
        ok = await n.send(f"{text}\n{url}" if url else text)
        activity.emit("notify", "Telegram: " + text[:80], job=job_id, connector="telegram", agent="olead")
        return ok
    except Exception:
        return False


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
    out = {k: job[k] for k in ("id", "kind", "lane", "title", "stage", "status", "pending", "preview", "requestedTier",
                               "tier", "costs", "events", "createdAt", "deadlineAt") if k in job}
    # JSONB does not keep key order, so the order comes from the pipeline config.
    order = [st["name"] for st in cfg.pipeline.get("stages", [])]
    st = job.get("stages") or {}  # a malformed row must not break the whole list
    names = [n for n in order if n in st] + [n for n in st if n not in order]
    out["stages"] = [{"name": n, **st[n]} for n in names]
    out["brief"] = job.get("brief", {})
    out["parkReason"] = job.get("parkReason")
    out["lane"] = job.get("lane", "build")
    out["production"] = job.get("production")
    out["ownerClicksNeeded"] = int(cfg.exposure.get("tier1_owner_clicks", 3))
    if approvals is not None:
        out["approvals"] = approvals
    if evidence is not None:
        out["evidence"] = evidence
    return out


def minutes_left(job: dict) -> float:
    return (job.get("deadlineAt", 0) - time.time() * 1000) / 60000
