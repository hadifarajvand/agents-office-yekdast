"""T1.6: a notification counts as sent only after it was sent; park reasons carry the cause."""
import asyncio
import types

from app import db
from app.pipeline import jobs, ports


class _N:
    enabled = True

    def __init__(self, ok):
        self.ok, self.sent = ok, 0

    async def send(self, text):
        self.sent += 1
        return self.ok


def _job():
    j = jobs.new_job("client", "Notify me", {"title": "Notify me"}, requested_tier=0, lane="build")
    asyncio.run(db.save_job(j))
    return j["id"]


def test_failed_send_is_retried_not_marked_sent(fake_db, monkeypatch):
    n = _N(False)
    monkeypatch.setattr(ports, "get_deps", lambda: types.SimpleNamespace(notifier=n))
    jid = _job()
    assert asyncio.run(jobs.notify_once(jid, "k", "hi")) is False
    n.ok = True
    assert asyncio.run(jobs.notify_once(jid, "k", "hi")) is True
    assert asyncio.run(jobs.notify_once(jid, "k", "hi")) is False and n.sent == 2


def test_park_reason_carries_a_redacted_cause():
    from app.pipeline.api import crash_reason
    r = crash_reason(RuntimeError("boom api_key=sk-abc123456789 failed"))
    assert "RuntimeError" in r and "boom" in r and "sk-abc123456789" not in r
