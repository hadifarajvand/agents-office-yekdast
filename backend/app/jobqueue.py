"""Job queue: graph execution runs in an `arq` worker, not in the API process.

Off by default (AO_QUEUE unset): the API runs the graph in-process as before. With AO_QUEUE=1
every start/resume/kill is enqueued on Redis (REDIS_URL, default redis://127.0.0.1:6379) and the
worker (`arq app.jobqueue.WorkerSettings`) drives it. State stays in Postgres, so restarting
either process loses nothing: an interrupted job is parked by the worker on boot and the owner
presses Retry (decision in PLAN.md). No automatic retries: max_tries=1.
"""
from __future__ import annotations

import asyncio
import logging
import os
import socket
import time

from arq import create_pool
from arq.connections import RedisSettings

log = logging.getLogger("agents_office.queue")
_pool = None
_degraded: dict | None = None  # set while the API is driving work in-process because the queue refused it


def enabled() -> bool:
    return os.environ.get("AO_QUEUE") == "1"


def status() -> dict:
    """For /api/health: is the queue on, and is the API quietly doing the worker's job because it is down."""
    d = _degraded
    return {"enabled": enabled(), "degraded": d is not None, "since": d["at"] if d else None, "last": d["text"] if d else ""}


def redis_settings() -> RedisSettings:
    return RedisSettings.from_dsn(os.environ.get("REDIS_URL", "redis://127.0.0.1:6379"))


async def _enqueue(fn: str, what: str, *args, job_id: str) -> bool:
    """True when the worker has the work; False means the caller should run it in-process.
    One driver per id: arq refuses a second job with the same id while one is queued or running,
    so a double-clicked approval (or a kill sent mid-run) never puts two drivers on one run.
    A kill is cooperative anyway: it sets the status first and the running stage stops on it."""
    global _pool, _degraded
    try:
        if _pool is None:
            _pool = await create_pool(redis_settings())
        queued = await _pool.enqueue_job(fn, *args, _job_id=job_id)
        if queued is None:
            log.info("%s already has a driver in the worker; not queuing a second", what)
        _degraded = None
        return True
    except Exception as e:
        log.exception("queue unavailable, running %s in the API process", what)
        text = f"queue unavailable ({type(e).__name__}); {what} runs in the API process, without the worker's restart safety"
        _degraded = {"at": int(time.time() * 1000), "text": text}
        from . import activity  # the feed the Jobs screen and the office header read
        activity.emit("queue", text, connector="redis", level="warn")
        return False


async def enqueue(job_id: str, payload) -> bool:
    return await _enqueue("drive_job", f"job {job_id}", job_id, payload, job_id=f"drive-{job_id}")


async def enqueue_task(task_id: str, kind: str, feedback: str | None, approve: bool, key: str) -> bool:
    """A chat task, a routine run or a resume after the owner's decision. `key` makes the id unique per run."""
    return await _enqueue("drive_task", f"task {task_id}", task_id, kind, feedback, approve,
                          job_id=f"task-{task_id}-{key}")


STREAM = "ao:activity"
_cursor: str | None = None  # API side: id of the last worker event already copied into this process


def sink_to(redis):
    """Worker side: forward every activity event to the API process through a capped Redis stream."""
    import asyncio
    import json

    def sink(ev: dict) -> None:
        try:
            asyncio.get_running_loop().create_task(redis.xadd(STREAM, {"e": json.dumps(ev)}, maxlen=400, approximate=True))
        except RuntimeError:
            pass  # no running loop: the event stays in the worker's own buffer
    return sink


async def pull_activity() -> None:
    """API side: copy new worker events into this process's activity buffer (no-op when the queue is off)."""
    global _cursor, _pool
    if not enabled():
        return
    import json

    from . import activity
    try:
        if _pool is None:
            _pool = await create_pool(redis_settings())
        if _cursor is None:  # first call: start at the current end, not at history
            last = await _pool.xrevrange(STREAM, count=1)
            _cursor = last[0][0].decode() if last else "0"
            return
        for _stream, entries in await _pool.xread({STREAM: _cursor}, count=200):
            for eid, fields in entries:
                _cursor = eid.decode()
                activity.ingest(json.loads(fields[b"e"]))
    except Exception:
        log.debug("could not read worker activity", exc_info=True)


async def close() -> None:
    global _pool
    if _pool is not None:
        await _pool.close()
        _pool = None


async def drive_job(_ctx, job_id: str, payload) -> None:
    from .pipeline.api import _drive
    await _drive(job_id, payload)


async def drive_task(_ctx, task_id: str, kind: str, feedback: str | None, approve: bool) -> None:
    from . import main as m
    await m.drive_task(task_id, kind, feedback, approve)


LOCK_KEY = "ao:worker-lock"
LOCK_TTL = 30  # seconds; renewed every LOCK_TTL/3 while the worker lives


def _text(v) -> str:
    return v.decode() if isinstance(v, bytes) else str(v)


async def take_lock(redis) -> str:
    """One worker only: park_interrupted() on boot parks every `running` job, so a second worker
    would park the first one's live jobs. A second worker therefore refuses to start."""
    me = f"{socket.gethostname()}:{os.getpid()}"
    if not await redis.set(LOCK_KEY, me, nx=True, ex=LOCK_TTL):
        holder = _text(await redis.get(LOCK_KEY) or "unknown")
        raise SystemExit(
            f"another worker already holds {LOCK_KEY} ({holder}); refusing to start a second one. "
            f"Stop it first (scripts/stop.sh), or wait up to {LOCK_TTL}s if it crashed.")
    return me


async def keep_lock(redis, me: str) -> None:
    while True:
        await asyncio.sleep(LOCK_TTL / 3)
        try:
            held = await redis.get(LOCK_KEY)
            if held is None:
                await redis.set(LOCK_KEY, me, nx=True, ex=LOCK_TTL)
            elif _text(held) == me:
                await redis.expire(LOCK_KEY, LOCK_TTL)
            else:
                log.error("worker lock now belongs to %s; this worker should be stopped", _text(held))
        except asyncio.CancelledError:
            raise
        except Exception:
            log.exception("could not renew the worker lock")


async def release_lock(redis, me: str) -> None:
    try:
        if _text(await redis.get(LOCK_KEY) or "") == me:
            await redis.delete(LOCK_KEY)
    except Exception:
        log.exception("could not release the worker lock")


async def on_startup(ctx) -> None:
    from . import logsetup
    logsetup.configure()
    ctx["lock_owner"] = await take_lock(ctx["redis"])
    ctx["lock_task"] = asyncio.create_task(keep_lock(ctx["redis"], ctx["lock_owner"]))
    from langgraph.checkpoint.postgres.aio import AsyncPostgresSaver

    from . import db, llm
    from . import main as m
    from .deps import build_deps
    from .pipeline import api as pipeline_api
    from .pipeline import graph as pipeline_graph
    from .pipeline.ports import set_deps
    pool = await db.open_pool()
    saver = AsyncPostgresSaver(pool)
    await saver.setup()
    from .graph import engine
    engine.compile_graph(checkpointer=saver)  # chat tasks and routine runs pause and resume on it
    pipeline_graph.compile_pipeline(checkpointer=saver)
    set_deps(build_deps())
    llm.on_usage(m._record_cost)
    from . import activity
    activity._sink = sink_to(await create_pool(redis_settings()))
    try:  # the same GitHub read tools the API attaches at boot
        from .connectors import github
        m.mcp_registry.attach_tools("github", await github.read_tools(), name="GitHub")
    except Exception as e:
        log.info("GitHub tools not attached in the worker: %s", e)
    n = await pipeline_api.park_interrupted()
    if n:
        log.warning("parked %d job(s) interrupted by the last worker stop", n)
    n = await db.fail_interrupted_tasks()
    if n:
        log.warning("marked %d task(s) interrupted by the last worker stop as failed", n)


async def on_shutdown(ctx) -> None:
    from . import db
    if ctx.get("lock_task"):
        ctx["lock_task"].cancel()
        await release_lock(ctx["redis"], ctx["lock_owner"])
    await db.close_pool()


class WorkerSettings:
    functions = [drive_job, drive_task]
    on_startup = on_startup
    on_shutdown = on_shutdown
    redis_settings = redis_settings()
    max_jobs = 3
    max_tries = 1
    job_timeout = 4 * 3600
    keep_result = 0
