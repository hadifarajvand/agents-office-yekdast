"""One arq worker at a time: a second one refuses to start instead of parking the first one's jobs."""
import asyncio

import pytest

from app import jobqueue


class FakeRedis:
    def __init__(self):
        self.kv, self.ttl = {}, {}

    async def set(self, k, v, nx=False, ex=None):
        if nx and k in self.kv:
            return None
        self.kv[k], self.ttl[k] = v.encode(), ex
        return True

    async def get(self, k):
        return self.kv.get(k)

    async def expire(self, k, s):
        self.ttl[k] = s

    async def delete(self, k):
        self.kv.pop(k, None)


async def test_second_worker_refuses_to_start_and_names_the_holder():
    r = FakeRedis()
    first = await jobqueue.take_lock(r)
    with pytest.raises(SystemExit) as e:
        await jobqueue.take_lock(r)
    assert first in str(e.value) and "refusing to start a second one" in str(e.value)
    assert r.kv[jobqueue.LOCK_KEY] == first.encode()  # the first worker's lock is untouched


async def test_lock_expires_so_a_crashed_worker_does_not_block_forever():
    r = FakeRedis()
    await jobqueue.take_lock(r)
    assert r.ttl[jobqueue.LOCK_KEY] == jobqueue.LOCK_TTL


async def test_release_only_removes_the_lock_you_own():
    r = FakeRedis()
    me = await jobqueue.take_lock(r)
    await jobqueue.release_lock(r, "someone-else:1")
    assert jobqueue.LOCK_KEY in r.kv
    await jobqueue.release_lock(r, me)
    assert jobqueue.LOCK_KEY not in r.kv
    await jobqueue.take_lock(r)  # free again for the next worker


async def test_keep_lock_renews_and_retakes_a_vanished_lock(monkeypatch):
    r = FakeRedis()
    me = await jobqueue.take_lock(r)
    r.ttl[jobqueue.LOCK_KEY] = 1
    monkeypatch.setattr(jobqueue, "LOCK_TTL", 0.03)
    t = asyncio.create_task(jobqueue.keep_lock(r, me))
    await asyncio.sleep(0.05)
    assert r.ttl[jobqueue.LOCK_KEY] == 0.03
    r.kv.clear()
    await asyncio.sleep(0.05)
    assert r.kv[jobqueue.LOCK_KEY] == me.encode()
    t.cancel()
