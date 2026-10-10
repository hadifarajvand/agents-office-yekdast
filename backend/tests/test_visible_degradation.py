"""Failures the owner can see (MASTER_PLAN Part G, S6: TK-7, F-18, F-03, deps.py).

A degraded mode that only writes a log line is invisible when the owner is looking at the Jobs screen or
the phone. Three things change here:
  - the API falling back to in-process execution because Redis is down says so in the activity feed, on the
    job, and in /api/health;
  - a job parked by a restart tells the owner (once per restart), like every other park does;
  - /api/health says which of deploy / promote / web / notify / worker are real, not placeholders.
"""
from __future__ import annotations

import pytest
from fastapi.testclient import TestClient

from app import activity, db, deps as deps_mod, jobqueue
from app.pipeline import api as pipeline_api
from app.pipeline import jobs
from app.pipeline.ports import Deps, set_deps


class Notifier:
    enabled = True

    def __init__(self):
        self.sent: list[str] = []

    async def send(self, text):
        self.sent.append(text)
        return True


class Null:
    enabled = False


class Fake:
    """Stands in for a real adapter: anything that is not `Unconfigured` counts as configured."""


@pytest.fixture(autouse=True)
def _reset(monkeypatch):
    monkeypatch.setattr(jobqueue, "_pool", None)
    monkeypatch.setattr(jobqueue, "_degraded", None, raising=False)
    yield
    set_deps(None)


def events_since(seq: int) -> list[dict]:
    return activity.since(seq)["events"]


async def running_job(title="Bakery site") -> str:
    job = jobs.new_job("client", title, {"title": title}, requested_tier=0, lane="build")
    job["status"] = "running"
    await db.save_job(job)
    return job["id"]


# ---------- F-18: the in-process fallback is loud ----------
async def test_a_queue_that_is_down_is_reported_in_the_activity_feed_and_in_status(monkeypatch):
    async def down(*a, **k):
        raise ConnectionRefusedError("redis is not there")
    monkeypatch.setattr(jobqueue, "create_pool", down)
    seq = activity.since(0)["seq"]
    assert await jobqueue.enqueue("abc123", None) is False
    ev = [e for e in events_since(seq) if e["kind"] == "queue"]
    assert len(ev) == 1 and ev[0]["level"] == "warn" and "API process" in ev[0]["text"]
    assert "ConnectionRefusedError" in ev[0]["text"] and "abc123" in ev[0]["text"]
    st = jobqueue.status()
    assert st["degraded"] is True and st["since"] and "ConnectionRefusedError" in st["last"]


async def test_a_queue_that_recovers_clears_the_degraded_flag(monkeypatch):
    class Pool:
        async def enqueue_job(self, *a, **k):
            return object()
    calls = {"n": 0}

    async def flaky(*a, **k):
        calls["n"] += 1
        if calls["n"] == 1:
            raise OSError("down")
        return Pool()
    monkeypatch.setattr(jobqueue, "create_pool", flaky)
    assert await jobqueue.enqueue("j1", None) is False and jobqueue.status()["degraded"] is True
    assert await jobqueue.enqueue("j1", None) is True and jobqueue.status()["degraded"] is False


def test_status_when_the_queue_is_off_is_not_degraded(monkeypatch):
    monkeypatch.delenv("AO_QUEUE", raising=False)
    assert jobqueue.status() == {"enabled": False, "degraded": False, "since": None, "last": ""}


async def test_dispatch_falls_back_in_process_and_writes_an_event_on_the_job(fake_db, monkeypatch):
    monkeypatch.setenv("AO_QUEUE", "1")
    spawned = []
    monkeypatch.setattr(pipeline_api, "_spawn", lambda coro: (coro.close(), spawned.append(1)))

    async def refused(job_id, payload):
        return False
    monkeypatch.setattr(jobqueue, "enqueue", refused)
    jid = await running_job()
    await pipeline_api.dispatch(jid, None)
    assert spawned == [1]
    texts = [e["text"] for e in (await db.get_job(jid))["events"]]
    assert any("queue unavailable" in t and "API process" in t for t in texts)


async def test_dispatch_through_a_working_queue_writes_no_fallback_event(fake_db, monkeypatch):
    monkeypatch.setenv("AO_QUEUE", "1")
    spawned = []
    monkeypatch.setattr(pipeline_api, "_spawn", lambda coro: (coro.close(), spawned.append(1)))

    async def accepted(job_id, payload):
        return True
    monkeypatch.setattr(jobqueue, "enqueue", accepted)
    jid = await running_job()
    await pipeline_api.dispatch(jid, None)
    assert spawned == [] and not (await db.get_job(jid)).get("events")


# ---------- F-03: a boot park tells the owner ----------
async def test_a_job_parked_by_a_restart_notifies_the_owner_once_per_restart(fake_db):
    n = Notifier()
    set_deps(Deps(chat_json=None, notifier=n))
    jid = await running_job("Tip splitter")
    assert await pipeline_api.park_interrupted() == 1
    job = await db.get_job(jid)
    assert job["status"] == "parked" and job["parkCount"] == 1
    assert len(n.sent) == 1 and "Tip splitter" in n.sent[0] and "restart" in n.sent[0]
    # the owner presses Retry, the job runs, the process restarts again: that is a new park, a new message
    await jobs.touch(jid, status="running")
    assert await pipeline_api.park_interrupted() == 1
    assert len(n.sent) == 2 and (await db.get_job(jid))["parkCount"] == 2
    # the sweep never re-announces a job that is already parked
    assert await pipeline_api.park_interrupted() == 0 and len(n.sent) == 2


async def test_a_dead_notification_channel_never_stops_the_boot_sweep(fake_db):
    class Broken:
        enabled = True

        async def send(self, text):
            raise RuntimeError("telegram is down")
    set_deps(Deps(chat_json=None, notifier=Broken()))
    a, b = await running_job("A"), await running_job("B")
    assert await pipeline_api.park_interrupted() == 2
    assert {(await db.get_job(i))["status"] for i in (a, b)} == {"parked"}


async def test_the_boot_sweep_still_parks_when_deps_are_not_configured_yet(fake_db):
    set_deps(None)  # notify_once asks for the deps; a missing set must not stop the park
    jid = await running_job()
    assert await pipeline_api.park_interrupted() == 1
    assert (await db.get_job(jid))["status"] == "parked"


# ---------- deps.py: which pieces are real ----------
def test_readiness_tells_a_real_adapter_from_a_placeholder():
    d = Deps(chat_json=None, worker=Fake(), deployer=deps_mod.Unconfigured("the Dokploy deployer", "set DOKPLOY_URL"),
             promoter=Fake(), web=type("W", (), {"can_search": False})(), notifier=Null())
    r = deps_mod.readiness(d)
    assert r["worker"]["ready"] is True and r["promoter"]["ready"] is True
    assert r["deployer"] == {"ready": False, "why": "set DOKPLOY_URL"}
    assert r["web"]["ready"] is False and r["web"]["why"]
    assert r["notifier"]["ready"] is False and r["notifier"]["why"]


def test_readiness_when_everything_is_bound():
    d = Deps(chat_json=None, worker=Fake(), deployer=Fake(), promoter=Fake(),
             web=type("W", (), {"can_search": True})(), notifier=Notifier())
    assert all(v["ready"] for v in deps_mod.readiness(d).values())
    assert all(v["why"] == "" for v in deps_mod.readiness(d).values())


def test_readiness_names_every_piece_the_pipeline_can_lack():
    assert set(deps_mod.readiness(Deps(chat_json=None))) == {"worker", "deployer", "promoter", "web", "notifier"}


@pytest.fixture
def api(fake_db, isolated_brain):
    from app.main import app
    return TestClient(app, headers={"X-AO-Client": "office", "Origin": "http://localhost:4520"})


def test_health_shows_which_pieces_are_real_and_the_queue_state(api):
    set_deps(Deps(chat_json=None, worker=Fake(), deployer=deps_mod.Unconfigured("the Dokploy deployer", "set DOKPLOY_URL"),
                  promoter=Fake(), notifier=Null()))
    body = api.get("/api/health").json()
    assert body["deps"]["deployer"]["ready"] is False and body["deps"]["worker"]["ready"] is True
    assert set(body["queue"]) == {"enabled", "degraded", "since", "last"}


def test_health_still_answers_before_the_deps_are_built(api):
    set_deps(None)
    assert api.get("/api/health").json()["deps"] == {}


def test_health_never_carries_a_secret(api, monkeypatch):
    from app.connectors.notify import TelegramNotifier
    set_deps(Deps(chat_json=None, worker=Fake(), notifier=TelegramNotifier("123:SECRET-TOKEN", "42")))
    text = api.get("/api/health").text
    assert "SECRET-TOKEN" not in text
