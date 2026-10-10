"""T1.3: a job parked by a restart must read `running` once its driver picks it up (F-03)."""
import asyncio

from app import db
from app.pipeline import api, jobs


class _Graph:
    def __init__(self):
        self.seen = None

    async def ainvoke(self, payload, config=None):
        self.seen = (await db.get_job(config["configurable"]["thread_id"].removeprefix("job-")))["status"]


def _parked(reason):
    job = jobs.new_job("client", "Park race", {"title": "Park race"}, requested_tier=0, lane="build")
    job["status"], job["parkReason"] = "parked", reason
    asyncio.run(db.save_job(job))
    return job["id"]


def test_restart_parked_job_is_running_when_driven(fake_db, monkeypatch):
    g = _Graph()
    monkeypatch.setattr(api, "compiled", lambda: g)
    jid = _parked(api.RESTART_REASON)
    asyncio.run(api._drive(jid, None))
    job = asyncio.run(db.get_job(jid))
    assert g.seen == "running" and not job.get("parkReason")


def test_other_parks_are_left_alone(fake_db, monkeypatch):
    g = _Graph()
    monkeypatch.setattr(api, "compiled", lambda: g)
    jid = _parked("budget reached")
    asyncio.run(api._drive(jid, None))
    assert g.seen == "parked"


def test_a_crash_parks_instead_of_failing(fake_db, monkeypatch):
    class Boom:
        async def ainvoke(self, *a, **k):
            raise RuntimeError("db down")
    monkeypatch.setattr(api, "compiled", lambda: Boom())
    jid = _parked("x")
    asyncio.run(api._drive(jid, None))
    job = asyncio.run(db.get_job(jid))
    assert job["status"] == "parked" and "RuntimeError" in job["parkReason"]
