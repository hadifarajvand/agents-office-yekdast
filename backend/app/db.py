"""Postgres state through one psycopg 3 connection pool.

The same pool backs the LangGraph checkpointer (main.lifespan), so the office has a
single Postgres driver. Schema changes live in app/migrations/NNN_*.sql and are
applied in order, once, by `migrate()`; `schema_version` records what ran.

Tests replace the public coroutines below with in-memory fakes (see tests/fakes.py),
so the function names and signatures here are the storage contract.
"""
from __future__ import annotations

import json
import os
import time
import uuid
import zlib
from pathlib import Path
from typing import Any

from psycopg.rows import dict_row
from psycopg.types.json import Jsonb
from psycopg_pool import AsyncConnectionPool

DATABASE_URL = (os.environ.get("DATABASE_URL", "postgresql://office:office@postgres:5432/office")
                .replace("postgresql+asyncpg://", "postgresql://")
                .replace("postgresql+psycopg://", "postgresql://"))
MIGRATIONS = Path(__file__).resolve().parent / "migrations"

_pool: AsyncConnectionPool | None = None


def pool_kwargs() -> dict:
    # autocommit + prepare_threshold=0 + dict_row are what AsyncPostgresSaver expects.
    return {"autocommit": True, "prepare_threshold": 0, "row_factory": dict_row}


async def open_pool(url: str | None = None, *, min_size: int = 1, max_size: int = 10) -> AsyncConnectionPool:
    global _pool
    if _pool is None:
        _pool = AsyncConnectionPool(url or DATABASE_URL, min_size=min_size, max_size=max_size,
                                    kwargs=pool_kwargs(), open=False)
        await _pool.open(wait=True, timeout=30)
        await migrate(_pool)
    return _pool


async def close_pool() -> None:
    global _pool
    if _pool is not None:
        await _pool.close()
        _pool = None


async def get_pool() -> AsyncConnectionPool:
    return _pool if _pool is not None else await open_pool()


async def migrate(pool: AsyncConnectionPool) -> list[str]:
    applied: list[str] = []
    async with pool.connection() as c:
        await c.execute("CREATE TABLE IF NOT EXISTS schema_version (name TEXT PRIMARY KEY, at DOUBLE PRECISION NOT NULL)")
        # Serialize concurrent starters on one advisory lock.
        await c.execute("SELECT pg_advisory_lock(4520001)")
        try:
            done = {r["name"] for r in await (await c.execute("SELECT name FROM schema_version")).fetchall()}
            for f in sorted(MIGRATIONS.glob("*.sql")):
                if f.name in done:
                    continue
                async with c.transaction():
                    await c.execute(f.read_text(), prepare=False)  # multi-statement file
                    await c.execute("INSERT INTO schema_version (name, at) VALUES (%s, %s)", (f.name, time.time()))
                applied.append(f.name)
        finally:
            await c.execute("SELECT pg_advisory_unlock(4520001)")
    return applied


def nid() -> str:
    return uuid.uuid4().hex[:12]


def now_ms() -> float:
    return time.time() * 1000


def _j(v):
    return json.loads(v) if isinstance(v, str) else v


# ---------- tasks ----------

async def list_tasks() -> list[dict]:
    p = await get_pool()
    async with p.connection() as c:
        rows = await (await c.execute("SELECT data FROM tasks ORDER BY updated_at ASC")).fetchall()
    return [_j(r["data"]) for r in rows]


async def get_task(task_id: str) -> dict | None:
    p = await get_pool()
    async with p.connection() as c:
        row = await (await c.execute("SELECT data FROM tasks WHERE id = %s", (task_id,))).fetchone()
    return _j(row["data"]) if row else None


async def save_task(task: dict) -> None:
    p = await get_pool()
    async with p.connection() as c:
        await c.execute(
            "INSERT INTO tasks (id, data, state, updated_at) VALUES (%s, %s, %s, %s) "
            "ON CONFLICT (id) DO UPDATE SET data = EXCLUDED.data, state = EXCLUDED.state, updated_at = EXCLUDED.updated_at",
            (task["id"], Jsonb(task), task.get("state", "next"), time.time()),
        )


async def claim_task(task_id: str, from_state: str, to_state: str) -> dict | None:
    """Atomically move a task from one state to another. Returns the updated task,
    or None when it was not in `from_state` (e.g. a second click on APPROVE)."""
    p = await get_pool()
    async with p.connection() as c:
        row = await (await c.execute(
            "UPDATE tasks SET state = %s, data = jsonb_set(data, '{state}', to_jsonb(%s::text)), updated_at = %s "
            "WHERE id = %s AND state = %s RETURNING data",
            (to_state, to_state, time.time(), task_id, from_state),
        )).fetchone()
    return _j(row["data"]) if row else None


async def delete_task(task_id: str) -> None:
    p = await get_pool()
    async with p.connection() as c:
        await c.execute("DELETE FROM tasks WHERE id = %s", (task_id,))


async def fail_interrupted_tasks() -> int:
    """On startup, tasks left in "doing" by a crash or restart can never finish;
    mark them failed so the UI does not wait on them forever."""
    p = await get_pool()
    async with p.connection() as c:
        rows = await (await c.execute(
            "UPDATE tasks SET state = 'done', "
            "data = data || jsonb_build_object('state','done','error',true,'result','Interrupted by a restart — run it again.','doneAt', %s::float8), "
            "updated_at = %s WHERE state = 'doing' RETURNING id",
            (now_ms(), time.time()),
        )).fetchall()
    return len(rows)


# ---------- routines ----------

async def load_routine_state() -> dict:
    p = await get_pool()
    async with p.connection() as c:
        rows = await (await c.execute("SELECT id, data FROM routine_state")).fetchall()
    return {r["id"]: _j(r["data"]) for r in rows}


async def save_routine_state(st: dict) -> None:
    """Upsert each routine's state and drop rows for routines that no longer exist.
    Row-level writes, so two writers no longer erase each other's routines."""
    p = await get_pool()
    async with p.connection() as c:
        async with c.transaction():
            for rid, data in st.items():
                await c.execute(
                    "INSERT INTO routine_state (id, data) VALUES (%s, %s) ON CONFLICT (id) DO UPDATE SET data = EXCLUDED.data",
                    (rid, Jsonb(data)),
                )
            await c.execute("DELETE FROM routine_state WHERE NOT (id = ANY(%s))", (list(st.keys()),))


async def claim_routine_slot(routine_id: str, due: float) -> bool:
    """Only one process fires a given due slot: record it and win on first insert."""
    p = await get_pool()
    key = f"routine-due:{routine_id}:{int(due)}"
    async with p.connection() as c:
        row = await (await c.execute(
            "INSERT INTO counters (name, value) VALUES (%s, 1) ON CONFLICT (name) DO NOTHING RETURNING value", (key,)
        )).fetchone()
    return row is not None


# ---------- jobs ----------

async def save_job(job: dict) -> None:
    p = await get_pool()
    async with p.connection() as c:
        await c.execute(
            "INSERT INTO jobs (id, kind, title, stage, status, data, created_at, updated_at) "
            "VALUES (%s, %s, %s, %s, %s, %s, %s, %s) ON CONFLICT (id) DO UPDATE SET "
            "title = EXCLUDED.title, stage = EXCLUDED.stage, status = EXCLUDED.status, data = EXCLUDED.data, "
            "updated_at = EXCLUDED.updated_at",
            (job["id"], job["kind"], job["title"], job["stage"], job["status"], Jsonb(job),
             job.get("createdAt", now_ms()), now_ms()),
        )


async def get_job(job_id: str) -> dict | None:
    p = await get_pool()
    async with p.connection() as c:
        row = await (await c.execute("SELECT data FROM jobs WHERE id = %s", (job_id,))).fetchone()
    return _j(row["data"]) if row else None


async def list_jobs() -> list[dict]:
    p = await get_pool()
    async with p.connection() as c:
        rows = await (await c.execute("SELECT data FROM jobs ORDER BY created_at ASC")).fetchall()
    return [_j(r["data"]) for r in rows]


async def record_approval(job_id: str, stage: str, role: str, verdict: str, note: str,
                          evidence: list, actor: str) -> bool:
    """Insert a decision; False if this role already decided this stage (idempotent)."""
    p = await get_pool()
    async with p.connection() as c:
        row = await (await c.execute(
            "INSERT INTO approvals (job_id, stage, role, verdict, note, evidence, actor, at) "
            "VALUES (%s, %s, %s, %s, %s, %s, %s, %s) ON CONFLICT DO NOTHING RETURNING role",
            (job_id, stage, role, verdict, note, Jsonb(evidence), actor, now_ms()),
        )).fetchone()
    return row is not None


async def clear_approvals(job_id: str, stage: str) -> None:
    """A stage that is re-run after a FAIL needs fresh decisions."""
    p = await get_pool()
    async with p.connection() as c:
        await c.execute("DELETE FROM approvals WHERE job_id = %s AND stage = %s", (job_id, stage))


async def list_approvals(job_id: str) -> list[dict]:
    p = await get_pool()
    async with p.connection() as c:
        rows = await (await c.execute(
            "SELECT job_id, stage, role, verdict, note, evidence, actor, at FROM approvals WHERE job_id = %s ORDER BY at",
            (job_id,))).fetchall()
    return [dict(r, evidence=_j(r["evidence"])) for r in rows]


async def add_evidence(job_id: str, stage: str, kind: str, title: str, ok: bool | None, body: Any,
                       evidence_id: str | None = None) -> str:
    """Upsert by id, so a node that re-runs after an interrupt does not duplicate rows."""
    eid = evidence_id or nid()
    p = await get_pool()
    async with p.connection() as c:
        await c.execute(
            "INSERT INTO evidence (id, job_id, stage, kind, title, ok, body, at) VALUES (%s,%s,%s,%s,%s,%s,%s,%s) "
            "ON CONFLICT (id) DO UPDATE SET title = EXCLUDED.title, ok = EXCLUDED.ok, body = EXCLUDED.body, at = EXCLUDED.at",
            (eid, job_id, stage, kind, title, ok, Jsonb(body), now_ms()),
        )
    return eid


async def list_evidence(job_id: str) -> list[dict]:
    p = await get_pool()
    async with p.connection() as c:
        rows = await (await c.execute(
            "SELECT id, stage, kind, title, ok, body, at FROM evidence WHERE job_id = %s ORDER BY at", (job_id,))).fetchall()
    return [dict(r, body=_j(r["body"])) for r in rows]


# ---------- audit, costs, counters ----------

async def audit(agent: str, dept: str, server: str, operation: str, resource: str, allowed: bool, reason: str = "") -> None:
    p = await get_pool()
    async with p.connection() as c:
        await c.execute(
            "INSERT INTO audit_log (at, agent, dept, server, operation, resource, allowed, reason) VALUES (%s,%s,%s,%s,%s,%s,%s,%s)",
            (time.time(), agent, dept, server, operation, resource, allowed, reason),
        )


async def record_cost(label: str, model_pinned: str, model_seen: str, input_tokens: int, output_tokens: int, usd: float) -> None:
    p = await get_pool()
    async with p.connection() as c:
        await c.execute(
            "INSERT INTO run_costs (at, label, model_pinned, model_seen, input_tokens, output_tokens, usd) VALUES (%s,%s,%s,%s,%s,%s,%s)",
            (time.time(), label, model_pinned, model_seen, input_tokens, output_tokens, usd),
        )


async def usage_window(hours: float = 5.0) -> dict:
    since = time.time() - hours * 3600
    p = await get_pool()
    async with p.connection() as c:
        row = await (await c.execute(
            "SELECT COUNT(*) AS runs, COALESCE(SUM(input_tokens + output_tokens), 0) AS tokens, "
            "COALESCE(SUM(usd), 0) AS usd, MIN(at) AS first FROM run_costs WHERE at >= %s", (since,))).fetchone()
    started = row["first"] or time.time()
    return {"runs": int(row["runs"]), "tokens": int(row["tokens"]), "usd": float(row["usd"]),
            "startedAt": started * 1000, "resetsAt": (started + hours * 3600) * 1000}


async def counter(name: str) -> int:
    p = await get_pool()
    async with p.connection() as c:
        row = await (await c.execute("SELECT value FROM counters WHERE name = %s", (name,))).fetchone()
    return int(row["value"]) if row else 0


async def bump_counter(name: str) -> int:
    p = await get_pool()
    async with p.connection() as c:
        row = await (await c.execute(
            "INSERT INTO counters (name, value) VALUES (%s, 1) ON CONFLICT (name) DO UPDATE SET value = counters.value + 1 RETURNING value",
            (name,))).fetchone()
    return int(row["value"])


def lock_key(*parts: str) -> int:
    return zlib.crc32(":".join(parts).encode()) & 0x7FFFFFFF
