"""Postgres-backed state: tasks, routine run-state, usage window.

Per the owner's "Postgres only" decision, this replaces data/tasks.json and
data/routines.json entirely — no flat files alongside the DB.
"""
from __future__ import annotations

import json
import os
import time
import uuid
from typing import Any

import asyncpg

DATABASE_URL = os.environ.get("DATABASE_URL", "postgresql://office:office@postgres:5432/office").replace("postgresql+asyncpg://", "postgresql://")

_pool: asyncpg.Pool | None = None


async def get_pool() -> asyncpg.Pool:
    global _pool
    if _pool is None:
        _pool = await asyncpg.create_pool(DATABASE_URL)
        await _init(_pool)
    return _pool


async def _init(pool: asyncpg.Pool) -> None:
    async with pool.acquire() as c:
        await c.execute("""
            CREATE TABLE IF NOT EXISTS tasks (
                id TEXT PRIMARY KEY,
                data JSONB NOT NULL,
                updated_at DOUBLE PRECISION NOT NULL
            )
        """)
        await c.execute("""
            CREATE TABLE IF NOT EXISTS routine_state (
                id TEXT PRIMARY KEY,
                data JSONB NOT NULL
            )
        """)
        await c.execute("""
            CREATE TABLE IF NOT EXISTS kv (
                key TEXT PRIMARY KEY,
                data JSONB NOT NULL
            )
        """)


def nid() -> str:
    return uuid.uuid4().hex[:12]


async def list_tasks() -> list[dict]:
    pool = await get_pool()
    rows = await pool.fetch("SELECT data FROM tasks ORDER BY updated_at ASC")
    return [json.loads(r["data"]) if isinstance(r["data"], str) else r["data"] for r in rows]


async def get_task(task_id: str) -> dict | None:
    pool = await get_pool()
    row = await pool.fetchrow("SELECT data FROM tasks WHERE id = $1", task_id)
    if not row:
        return None
    return json.loads(row["data"]) if isinstance(row["data"], str) else row["data"]


async def save_task(task: dict) -> None:
    pool = await get_pool()
    await pool.execute(
        "INSERT INTO tasks (id, data, updated_at) VALUES ($1, $2, $3) "
        "ON CONFLICT (id) DO UPDATE SET data = $2, updated_at = $3",
        task["id"], json.dumps(task), time.time(),
    )


async def delete_task(task_id: str) -> None:
    pool = await get_pool()
    await pool.execute("DELETE FROM tasks WHERE id = $1", task_id)


async def load_routine_state() -> dict:
    pool = await get_pool()
    rows = await pool.fetch("SELECT id, data FROM routine_state")
    return {r["id"]: (json.loads(r["data"]) if isinstance(r["data"], str) else r["data"]) for r in rows}


async def save_routine_state(st: dict) -> None:
    pool = await get_pool()
    async with pool.acquire() as c:
        async with c.transaction():
            await c.execute("DELETE FROM routine_state")
            for rid, data in st.items():
                await c.execute("INSERT INTO routine_state (id, data) VALUES ($1, $2)", rid, json.dumps(data))


async def kv_get(key: str, default: Any = None) -> Any:
    pool = await get_pool()
    row = await pool.fetchrow("SELECT data FROM kv WHERE key = $1", key)
    if not row:
        return default
    return json.loads(row["data"]) if isinstance(row["data"], str) else row["data"]


async def kv_set(key: str, value: Any) -> None:
    pool = await get_pool()
    await pool.execute(
        "INSERT INTO kv (key, data) VALUES ($1, $2) ON CONFLICT (key) DO UPDATE SET data = $2",
        key, json.dumps(value),
    )
