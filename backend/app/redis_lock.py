"""Task 5: a Redis-backed distributed lock so two backend replicas sharing one
Postgres and one Redis don't both fire the same due routine. Postgres stays the
system of record for routine_state (nextAt/lastAt/runs); Redis is purely a
short-lived claim on "I'm firing this routine's current due slot" — nothing
here is durable state. Run *serialization* within a single process is still
app/main.py's asyncio.Lock; this only stops the double-fire across replicas.
"""
from __future__ import annotations

import os

import redis.asyncio as redis

REDIS_URL = os.environ.get("REDIS_URL", "redis://localhost:6379/0")
LOCK_TTL_SECONDS = 60

_client: redis.Redis | None = None


def get_client() -> redis.Redis:
    global _client
    if _client is None:
        _client = redis.from_url(REDIS_URL, decode_responses=True)
    return _client


async def claim_due_slot(routine_id: str, due_at: float) -> bool:
    """True if this replica won the claim on this routine's current due
    timestamp and should fire it; False if another replica already has it.
    Keyed by (routine_id, due_at) rather than just routine_id so the claim
    naturally expires and releases once that slot's run is recorded and
    advance() computes the next one."""
    key = f"routine-due:{routine_id}:{int(due_at)}"
    return bool(await get_client().set(key, "1", nx=True, ex=LOCK_TTL_SECONDS))
