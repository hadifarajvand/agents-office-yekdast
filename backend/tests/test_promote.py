"""Production promotion: owner-only, two steps, and only for a job whose record proves it is ready."""
from __future__ import annotations

import io
import tarfile

import pytest
from fastapi.testclient import TestClient

from app import db
from app.connectors import promote as pm
from app.pipeline import jobs
from app.pipeline.ports import Deps, set_deps


class FakePromoter:
    def __init__(self, healthy=True):
        self.healthy, self.prepared, self.deployed = healthy, [], []

    async def prepare(self, job, bundle, domain):
        self.prepared.append((job["id"], bundle, domain))
        return {"repo": "https://github.com/acme/x.git", "app_id": "app-1", "url": f"https://{domain}"}

    async def deploy(self, prod):
        self.deployed.append(prod["app_id"])
        return {"ok": self.healthy, "status": 200 if self.healthy else 502}


async def finished_job(tmp_path, *, build_ok=True, fake=False, status="done"):
    job = jobs.new_job("client", "Bakery ordering site", {"title": "Bakery ordering site"})
    job.update(status=status, preview={"app_id": "prev-1", "tier": 0})
    await db.save_job(job)
    out = tmp_path / "out"
    out.mkdir(exist_ok=True)
    data = b"DATABASE_URL=\nBETTER_AUTH_SECRET=\n# comment\nlower=1\n"
    with tarfile.open(out / "tree.tar.gz", "w:gz") as t:
        info = tarfile.TarInfo("./.env.example")
        info.size = len(data)
        t.addfile(info, io.BytesIO(data))
    name = "fake worker: nothing was built or tested" if fake else "unit tests pass (npm test)"
    await db.add_evidence(job["id"], "build", "check", name, build_ok, {"attempt": 0}, evidence_id=f'{job["id"]}:b:c')
    await db.add_evidence(job["id"], "build", "patch", "build result", True,
                          {"attempt": 0, "patch_path": str(out / "patch.bundle")}, evidence_id=f'{job["id"]}:b:p')
    await db.add_evidence(job["id"], "security", "check", "no secrets in the code", True, {"attempt": 0}, evidence_id=f'{job["id"]}:s:c')
    return job["id"]


@pytest.fixture
def client(fake_db):
    p = FakePromoter()
    set_deps(Deps(chat_json=None, promoter=p))
    from app.main import app
    c = TestClient(app, headers={"X-AO-Client": "office", "Origin": "http://localhost:4520"})
    c.promoter = p
    yield c
    set_deps(None)


async def test_a_ready_job_is_prepared_then_deployed_and_probed(client, tmp_path):
    jid = await finished_job(tmp_path)
    st = client.get(f"/api/jobs/{jid}/promote").json()
    assert st["ready"] is True and len(st["checklist"]) == 4
    r = client.post(f"/api/jobs/{jid}/promote", json={"step": "deploy", "envConfirmed": True})
    assert r.status_code == 409  # prepare comes first
    r = client.post(f"/api/jobs/{jid}/promote", json={"step": "prepare", "domain": "Orders.Acme-Bakery.com"})
    assert r.status_code == 200
    prod = r.json()["production"]
    assert prod["state"] == "prepared" and prod["env"] == ["BETTER_AUTH_SECRET", "DATABASE_URL"]
    assert client.promoter.prepared[0][2] == "orders.acme-bakery.com" and client.promoter.deployed == []
    r = client.post(f"/api/jobs/{jid}/promote", json={"step": "deploy"})
    assert r.status_code == 400  # the owner must confirm the variables are set
    r = client.post(f"/api/jobs/{jid}/promote", json={"step": "deploy", "envConfirmed": True})
    assert r.status_code == 200 and r.json()["production"]["state"] == "live"
    assert (await db.get_job(jid))["production"]["url"] == "https://orders.acme-bakery.com"


async def test_an_unhealthy_deploy_is_reported_not_hidden(client, tmp_path):
    client.promoter.healthy = False
    jid = await finished_job(tmp_path)
    client.post(f"/api/jobs/{jid}/promote", json={"step": "prepare", "domain": "app.example.com"})
    r = client.post(f"/api/jobs/{jid}/promote", json={"step": "deploy", "envConfirmed": True})
    assert r.json()["ok"] is False and r.json()["production"]["state"] == "unhealthy"


@pytest.mark.parametrize("kw", [{"build_ok": False}, {"fake": True}, {"status": "waiting"}])
async def test_not_ready_jobs_are_refused(client, tmp_path, kw):
    jid = await finished_job(tmp_path, **kw)
    assert client.get(f"/api/jobs/{jid}/promote").json()["ready"] is False
    r = client.post(f"/api/jobs/{jid}/promote", json={"step": "prepare", "domain": "app.example.com"})
    assert r.status_code == 409 and "not ready" in r.json()["error"]
    assert client.promoter.prepared == []


@pytest.mark.parametrize("domain", ["", "localhost", "http://x.com", "a b.com", "x.c"])
async def test_a_bad_domain_is_refused(client, tmp_path, domain):
    jid = await finished_job(tmp_path)
    assert client.post(f"/api/jobs/{jid}/promote", json={"step": "prepare", "domain": domain}).status_code == 400


def test_nothing_an_agent_can_call_reaches_promotion():
    """Promotion lives behind the owner's HTTP endpoint only: no graph node, stage, spawn or bench path imports it."""
    import pathlib
    root = pathlib.Path(pm.__file__).resolve().parents[1]
    users = [p.relative_to(root).as_posix() for p in root.rglob("*.py") if "promote" in p.read_text() and p.name != "promote.py"]
    assert sorted(users) == ["deps.py", "pipeline/api.py", "pipeline/ports.py"]


def test_slug_is_safe_and_unique_per_job():
    assert pm.slug("Acme Bakery: Orders!!", "abcdef123") == "acme-bakery-orders-abcdef"
