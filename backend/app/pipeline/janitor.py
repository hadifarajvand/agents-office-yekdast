"""Takes expired previews down. Runs from the routine ticker in main.py."""
from __future__ import annotations

import logging

from .. import db
from . import jobs
from .ports import get_deps

log = logging.getLogger("agents_office.pipeline")


def is_expired(job: dict, now_ms: float) -> bool:
    p = job.get("preview") or {}
    return bool(p.get("app_id") and not p.get("stopped") and p.get("expiresAt") and p["expiresAt"] <= now_ms)


async def expire_previews(now_ms: float | None = None) -> int:
    now_ms = now_ms if now_ms is not None else db.now_ms()
    n = 0
    for job in await db.list_jobs():
        if not is_expired(job, now_ms):
            continue
        try:
            await get_deps().deployer.stop(job, job["preview"])
        except Exception:
            log.exception("could not stop the expired preview of job %s", job["id"])
            continue
        prev = {**job["preview"], "stopped": True, "url": None, "tier": 0}
        await jobs.touch(job["id"], preview=prev, tier=0)
        await jobs.event(job["id"], "preview expired and was taken down")
        n += 1
    return n
