"""Task 5: claim_due_slot() is the only thing standing between two backend
replicas and firing the same due routine twice. No host port is mapped to the
docker-compose Redis container from here (same situation as Postgres in
test_graph_integration.py), so this exercises the SET NX EX contract against a
minimal fake that implements just that contract, rather than a live server.
"""
import asyncio

from app import redis_lock


class FakeRedis:
    """Mimics redis.asyncio.Redis.set(key, val, nx=True, ex=...) just enough to
    prove claim_due_slot()'s mutual-exclusion logic: the first SET NX on a key
    wins, every later one on that same key fails until it's cleared."""

    def __init__(self):
        self._store: dict[str, str] = {}

    async def set(self, key, value, nx=False, ex=None):
        if nx and key in self._store:
            return None
        self._store[key] = value
        return True


def test_first_claim_wins_second_loses(monkeypatch):
    fake = FakeRedis()
    monkeypatch.setattr(redis_lock, "_client", fake)

    first = asyncio.run(redis_lock.claim_due_slot("overdue-reminders", 1000.0))
    second = asyncio.run(redis_lock.claim_due_slot("overdue-reminders", 1000.0))

    assert first is True
    assert second is False


def test_two_replicas_racing_the_same_due_slot_only_one_fires(monkeypatch):
    """Simulates the exact scenario Task 5 guards against: two processes
    (both backed by the same Redis) see the same routine due at the same
    timestamp in the same tick and both try to claim it."""
    fake = FakeRedis()
    monkeypatch.setattr(redis_lock, "_client", fake)

    async def replica_tries():
        return await redis_lock.claim_due_slot("overdue-reminders", 5000.0)

    async def both_replicas():
        return await asyncio.gather(replica_tries(), replica_tries())

    results = asyncio.run(both_replicas())
    assert sorted(results) == [False, True]


def test_different_due_slots_for_same_routine_each_get_their_own_claim(monkeypatch):
    """A later firing of the same routine (new nextAt after advance()) must
    not be blocked by a stale claim from an earlier run."""
    fake = FakeRedis()
    monkeypatch.setattr(redis_lock, "_client", fake)

    first_run = asyncio.run(redis_lock.claim_due_slot("overdue-reminders", 1000.0))
    next_run = asyncio.run(redis_lock.claim_due_slot("overdue-reminders", 2000.0))

    assert first_run is True
    assert next_run is True
