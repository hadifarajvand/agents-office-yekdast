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


# ---- T1.2: Docker errors are not timeouts; a cancelled run kills its container; job_timeout covers the build ----

def test_docker_error_is_not_reported_as_timeout():
    import pytest
    from app import sandbox

    class C:
        def wait(self, timeout=None):
            raise ConnectionError("docker daemon went away")
        def kill(self): pass
        def logs(self, **k): return b""
        def remove(self, force=False): pass

    class Client:
        class containers:
            @staticmethod
            def get(n): raise KeyError(n)
            @staticmethod
            def run(*a, **k): return C()

    with pytest.raises(ConnectionError):
        sandbox._run_blocking({"image": "i", "command": ["x"], "name": "ao-job-j"}, 5, Client())


def test_real_timeout_still_reports_timed_out():
    from app import sandbox
    from requests.exceptions import ReadTimeout

    class C:
        def wait(self, timeout=None):
            raise ReadTimeout("read timed out")
        def kill(self): pass
        def logs(self, **k): return b""
        def remove(self, force=False): pass

    class Client:
        class containers:
            @staticmethod
            def get(n): raise KeyError(n)
            @staticmethod
            def run(*a, **k): return C()

    res = sandbox._run_blocking({"image": "i", "command": ["x"], "name": "ao-job-j"}, 5, Client())
    assert res.timed_out and res.exit_code == 124


def test_cancelled_run_stops_its_container(monkeypatch):
    import threading
    from app import sandbox
    stopped = []
    release = threading.Event()
    monkeypatch.setattr(sandbox, "assert_hardened", lambda spec: None)
    monkeypatch.setattr(sandbox, "_run_blocking", lambda spec, t, c=None: (release.wait(5), sandbox.RunResult(0, ""))[1])
    monkeypatch.setattr(sandbox, "stop_job_container", lambda jid, client=None: stopped.append(jid) or True)

    async def go():
        t = asyncio.create_task(sandbox.run_container({"name": "ao-job-j9", "image": "i"}, 60))
        await asyncio.sleep(0.05)
        t.cancel()
        try:
            await t
        except asyncio.CancelledError:
            pass
        release.set()

    asyncio.run(go())
    assert stopped == ["j9"]


def test_job_timeout_covers_the_build_timeout():
    from app import jobqueue
    from app.config import load_config
    assert jobqueue.WorkerSettings.job_timeout > load_config().worker["timeout_minutes"] * 60
