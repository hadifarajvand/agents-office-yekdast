"""The owner's inbox and notifications: one list of what waits for the CEO, one message per event."""
from __future__ import annotations

import asyncio

import httpx
from fastapi.testclient import TestClient

from app import db
from app.connectors.notify import NullNotifier, TelegramNotifier
from app.pipeline import jobs
from app.pipeline.ports import Deps, get_deps, set_deps
from test_pipeline import GOOD_BRIEF, env, owner, start  # noqa: F401  (env is a fixture)


class FakeNotifier:
    enabled = True

    def __init__(self):
        self.sent: list[str] = []

    async def send(self, text):
        self.sent.append(text)
        return True


async def test_the_owner_is_told_once_per_gate_and_when_the_job_is_done(env):  # noqa: F811
    n = FakeNotifier()
    d = get_deps()
    set_deps(Deps(chat_json=d.chat_json, worker=d.worker, deployer=d.deployer, checks=d.checks, notifier=n))
    jid = await start(env)
    assert len(n.sent) == 1 and "decision at verify" in n.sent[0]
    for _ in range(6):
        if (await db.get_job(jid))["status"] != "waiting":
            break
        await owner(env, jid)
    gates = [t for t in n.sent if "decision at" in t]
    assert len(gates) == len(set(gates))  # a node that re-runs on resume does not message twice
    assert "done" in n.sent[-1] and "Promote" in n.sent[-1]


async def test_a_broken_channel_never_stops_a_job(env):  # noqa: F811
    class Broken:
        enabled = True

        async def send(self, text):
            raise RuntimeError("telegram is down")
    d = get_deps()
    set_deps(Deps(chat_json=d.chat_json, worker=d.worker, deployer=d.deployer, checks=d.checks, notifier=Broken()))
    jid = await start(env)
    assert (await db.get_job(jid))["status"] == "waiting"


def test_telegram_posts_the_text_and_never_logs_the_token(caplog):
    seen = {}

    def handler(req: httpx.Request):
        seen["url"], seen["body"] = str(req.url), req.content.decode()
        return httpx.Response(200, json={"ok": True})
    t = TelegramNotifier("123:SECRET", "42", http=httpx.AsyncClient(transport=httpx.MockTransport(handler)))
    assert asyncio.run(t.send("hello")) is True
    assert "SECRET" in seen["url"] and '"chat_id":"42"' in seen["body"].replace(" ", "")

    def down(req):
        raise httpx.ConnectError("no route")
    t = TelegramNotifier("123:SECRET", "42", http=httpx.AsyncClient(transport=httpx.MockTransport(down)))
    assert asyncio.run(t.send("hello")) is False
    assert "SECRET" not in caplog.text
    assert asyncio.run(NullNotifier().send("x")) is False


async def test_the_inbox_lists_what_waits_for_the_owner_in_priority_order(fake_db):
    def mk(title, **kw):
        j = jobs.new_job("client", title, {"title": title})
        j.update(kw)
        return j
    rows = [mk("idle", status="running"),
            mk("memo", status="done", lane="validate"),
            mk("gate", status="waiting", pending=[{"stage": "verify", "roles": ["owner"], "needsOwner": True}]),
            mk("lead-only", status="waiting", pending=[{"stage": "scope", "roles": ["dlead"], "needsOwner": False}]),
            mk("parked", status="parked", parkReason="budget"),
            mk("unhealthy", status="done", production={"state": "unhealthy"}),
            {"id": "broken-row"}]
    for r in rows:
        if "stages" in r:
            await db.save_job(r)
        else:
            fake_db.jobs[r["id"]] = r
    set_deps(Deps(chat_json=None))
    from app.main import app
    c = TestClient(app, headers={"X-AO-Client": "office", "Origin": "http://localhost:4520"})
    items = c.get("/api/inbox").json()
    set_deps(None)
    assert [(i["kind"], i["title"]) for i in items] == [("gate", "gate"), ("parked", "parked"),
                                                        ("production", "unhealthy"), ("memo", "memo")]
