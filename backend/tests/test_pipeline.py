"""The job pipeline end to end, with scripted model answers and fake worker/deployer/checks.

What these tests pin down:
  - the happy path at Tier 0 needs the owner only for the verdict and the handoff;
  - a gated (Tier 1) preview needs security + commercial keys, plus the owner for the first N;
  - builders can never approve exposure; the config validator rejects such wiring;
  - a lead FAIL sends the stage back with reasons, then parks the job after the loop limit;
  - a PASS needs cited evidence; a failed deterministic check fails without asking a model;
  - a model other than the pinned one voids a review; the per-job budget parks the job;
  - approvals are idempotent; kill takes the preview down.
"""
from __future__ import annotations

import re
from pathlib import Path

import pytest
from fastapi.testclient import TestClient
from langgraph.checkpoint.memory import InMemorySaver
from langgraph.types import Command

from app import db, llm
from app.config import load_config
from app.pipeline import exposure as exp
from app.pipeline import jobs
from app.pipeline.api import thread
from app.pipeline.graph import compile_pipeline
from app.pipeline.ports import Deps, set_deps
from app.roster import defaults

GOOD_BRIEF = {"title": "Bakery site", "description": "A small ordering site for a bakery with a menu and an order form.",
              "client": "Acme Bakery", "deposit_ref": "INV-001 paid", "acceptance": "customers can place an order"}


class Script:
    """Scripted model answers, keyed by what the prompt is for."""
    def __init__(self):
        self.review_verdicts: dict[str, list[str]] = {}   # stage -> queue of verdicts ("PASS"/"FAIL"/"NOCITE")
        self.calls: list[str] = []
        self.systems: list[str] = []
        self.seat_calls: list[str] = []
        self.mismatch = False

    async def chat_json(self, system, user, *, role="drafts"):
        self.calls.append(role)
        self.systems.append(system)
        if '"finding":"2-4 sentences"' in system:
            self.seat_calls.append(re.search(r"You are ([A-Z &]+)", system).group(1).strip())
            return {"finding": "looks workable", "risks": ["one risk"], "confidence": "medium"}
        if "reviewing your own team's stage" in system:
            stage = re.search(r"Stage: (\w+)", user).group(1)
            q = self.review_verdicts.get(stage, [])
            v = q.pop(0) if q else "PASS"
            if self.mismatch:
                llm.current_meter.get().mismatches.append("pinned oc/mimo-v2.5-free, router answered with other-model")
            ids = re.findall(r"id=(\S+)", user)
            if v == "NOCITE":
                return {"verdict": "PASS", "reasons": ["looks fine"], "cites": []}
            if v == "PREFIX":  # what a free model does with "<job>:<stage>:<n>:<kind>": cites the first segment only
                return {"verdict": "PASS", "reasons": ["looks fine"], "cites": ["abc123def456"]}
            return {"verdict": v, "reasons": [f"{stage} {v.lower()}"], "cites": ids[:2]}
        if "verify whether a client job" in system:
            return {"deposit_real": True, "scope_clear": True, "price_fits_effort": True, "deadline_realistic": True,
                    "repeatable": True, "risks": [], "summary": "ok"}
        if "scope a small" in system:
            return {"acceptance_criteria": ["order form submits"], "tasks": ["build form"], "stack": "next", "estimate_hours": 6}
        if "Propose web search queries" in system:
            return {"queries": ["bakery order software", "bakery phone orders pain"]}
        if "extract market evidence" in system:
            return {"claims": [{"gate": "D1", "subject": "Acme Bakeries Pro", "tier": "T2", "quote": "costs $49 per month"}]}
        if "client handoff memo" in system:
            return {"summary": "done", "how_to_open": "open the link", "what_was_built": ["site"], "known_limits": [], "next_steps": []}
        raise AssertionError("unscripted prompt: " + system[:60])


class FakeWorker:
    def __init__(self):
        self.runs = 0
        self.exit_state = "ok"
        self.models = ["nemotron-3-ultra-free"]
        self.checks = [{"name": "unit tests pass (npm test)", "ok": True, "detail": "12 passed"}]
        self.briefs: list[dict] = []
        self.rechecks = 0
        self.recheck_results: list[list[dict]] = []

    async def recheck(self, job_dir, limits):
        self.rechecks += 1
        return self.recheck_results.pop(0) if self.recheck_results else self.checks

    async def run(self, job_dir, brief, limits):
        self.runs += 1
        self.briefs.append(brief)
        checks = self.checks.pop(0) if self.checks and isinstance(self.checks[0], list) else self.checks
        return {"patch_path": str(job_dir / "patch.bundle"), "log_path": str(job_dir / "log.txt"), "tokens": 1000,
                "usd": 0.01, "models_seen": self.models, "exit_state": self.exit_state, "checks": checks}


class FakeDeployer:
    def __init__(self):
        self.deployed = 0
        self.exposed: list[int] = []
        self.stopped = 0
        self.probe_ok = True
        self.auth_ok = True

    async def auth_configured(self, preview):
        return {"ok": self.auth_ok, "detail": "basic auth set" if self.auth_ok else "no auth layer"}

    async def deploy_preview(self, job, patch_path):
        self.deployed += 1
        return {"app_id": "app1", "internal_url": "http://app1.internal"}

    async def probe_unauthenticated(self, preview):
        return {"status": 401 if self.probe_ok else 200, "ok": self.probe_ok}

    async def apply_exposure(self, job, preview, tier):
        self.exposed.append(tier)
        return {"url": f"https://p{tier}.example.test"}

    async def stop(self, job, preview):
        self.stopped += 1


class FakeChecks:
    def __init__(self):
        self.ok = True

    async def scan(self, patch_path):
        return [{"name": "secret scan", "ok": self.ok, "detail": "0 hits" if self.ok else "1 hit"},
                {"name": "dependency audit", "ok": True, "detail": "0 vulnerabilities"}]


@pytest.fixture
def env(fake_db, tmp_path, monkeypatch):
    cfg = load_config()
    monkeypatch.setitem(cfg.sandbox, "jobs_dir", str(tmp_path / "jobs"))
    monkeypatch.setitem(cfg.pipeline, "live_departments", list(exp.ALL_DEPTS))  # these tests exercise every lead
    monkeypatch.setitem(cfg.pipeline, "seats_enabled", True)  # and the seat fan-out
    monkeypatch.setitem(cfg.pipeline, "spawn", {"enabled": True, "max_per_stage": 3})
    script, worker, dep, checks = Script(), FakeWorker(), FakeDeployer(), FakeChecks()
    set_deps(Deps(chat_json=script.chat_json, worker=worker, deployer=dep, checks=checks, jobs_dir=tmp_path))
    graph = compile_pipeline(InMemorySaver())
    yield type("Env", (), dict(script=script, worker=worker, dep=dep, checks=checks, graph=graph, db=fake_db, cfg=cfg))
    set_deps(None)


async def start(env, tier=0, brief=None, kind="client"):
    brief = dict(brief or GOOD_BRIEF)
    job = jobs.new_job(kind, brief["title"], brief, requested_tier=tier)
    await db.save_job(job)
    state = {"job_id": job["id"], "kind": kind, "brief": brief, "requested_tier": tier, "loops": {}, "feedback": "", "route": ""}
    await env.graph.ainvoke(state, config=thread(job["id"]))
    return job["id"]


async def owner(env, jid, verdict="PASS"):
    """The owner decides the stage the job is waiting at (what POST /gates does)."""
    job = await db.get_job(jid)
    stage = job["pending"][0]["stage"]
    assert exp.OWNER in job["pending"][0]["roles"], job["pending"]
    await db.record_approval(jid, stage, exp.OWNER, verdict, "", [], exp.OWNER)
    await env.graph.ainvoke(Command(resume={"owner": verdict}), config=thread(jid))
    return stage


async def run_to_end(env, jid, limit=12):
    for _ in range(limit):
        job = await db.get_job(jid)
        if job["status"] != "waiting":
            return job
        await owner(env, jid)
    raise AssertionError("never finished")


# ---------- configuration ----------

def test_shipped_pipeline_config_is_valid_and_separates_duties():
    cfg = load_config()
    assert exp.validate_config(cfg, defaults()) == []
    for role in ("exec-vp-engineering", "mlead", "devops-cd"):  # engineering, frontend, devops leads
        assert not exp.can_approve(cfg, role, "exposure")
    assert exp.can_approve(cfg, "sec-compliance", "exposure") and exp.can_approve(cfg, "exec-ceo-strategist", "exposure")
    assert exp.can_approve(cfg, exp.OWNER, "exposure")
    assert not exp.can_approve(cfg, "exec-vp-engineering", "preview")  # a lead approves only its own stage
    assert exp.can_approve(cfg, "devops-cd", "preview")


def test_validator_rejects_a_builder_as_exposure_key(monkeypatch):
    cfg = load_config()
    monkeypatch.setitem(cfg.exposure, "keys", {"security": "exec-vp-engineering", "commercial": "exec-ceo-strategist"})
    assert any("builders cannot approve exposure" in p for p in exp.validate_config(cfg, defaults()))
    monkeypatch.setitem(cfg.exposure, "keys", {"security": "sec-compliance", "commercial": "sec-compliance"})
    assert any("two different seats" in p for p in exp.validate_config(cfg, defaults()))


def test_roles_by_tier():
    cfg = load_config()
    assert exp.stage_roles(cfg, "exposure", tier=0) == []
    assert exp.stage_roles(cfg, "exposure", tier=1, owner_clicks=0) == ["sec-compliance", "exec-ceo-strategist", "owner"]
    assert exp.stage_roles(cfg, "exposure", tier=1, owner_clicks=3) == ["sec-compliance", "exec-ceo-strategist"]
    assert exp.stage_roles(cfg, "exposure", tier=2, owner_clicks=99) == ["sec-compliance", "exec-ceo-strategist", "owner"]
    assert exp.stage_roles(cfg, "verify") == ["exec-ceo-strategist", "owner"]
    assert exp.stage_roles(cfg, "build") == ["exec-vp-engineering"]


# ---------- the happy path ----------

async def test_tier0_job_needs_the_owner_only_for_verdict_and_handoff(env):
    jid = await start(env, tier=0)
    seen = []
    job = await db.get_job(jid)
    while job["status"] == "waiting":
        seen.append(await owner(env, jid))
        job = await db.get_job(jid)
    assert seen == ["verify", "handoff"]
    assert job["status"] == "done"
    assert all(s["state"] == "approved" for s in job["stages"].values())
    assert env.dep.deployed == 1 and env.dep.exposed == []
    assert job["costs"]["tokens"] >= 1000
    assert job["preview"] is None or job["preview"]["tier"] == 0


async def test_every_stage_records_a_lead_approval_with_evidence(env):
    jid = await start(env)
    await run_to_end(env, jid)
    approvals = {(a["stage"], a["role"]) for a in await db.list_approvals(jid)}
    for stage, lead in (("verify", "exec-ceo-strategist"), ("scope", "exec-vp-engineering"), ("build", "exec-vp-engineering"), ("security", "sec-compliance"),
                        ("preview", "devops-cd"), ("handoff", "exec-ceo-strategist")):
        assert (stage, lead) in approvals
    assert ("exposure", "sec-compliance") not in approvals  # Tier 0: no exposure decision at all


async def test_pipeline_work_shows_up_as_finished_display_only_tasks(env):
    jid = await start(env)
    await run_to_end(env, jid)
    mine = [t for t in await db.list_tasks() if t.get("jobId") == jid]
    assert mine and all(t["by"] == "pipeline" and t["pipeline"] and t["state"] == "done" for t in mine)
    assert {("engineering", "exec-vp-engineering"), ("secdata", "sec-compliance"), ("devops", "devops-cd")} <= {(t["dept"], t["agent"]) for t in mine}


# ---------- exposure ----------

async def test_gated_preview_needs_both_keys_and_the_owner_until_n_clicks(env):
    jid = await start(env, tier=1)
    job = await db.get_job(jid)
    assert job["pending"][0]["stage"] == "verify"
    await owner(env, jid)
    job = await db.get_job(jid)
    assert job["pending"][0]["stage"] == "exposure"
    assert job["pending"][0]["roles"] == ["owner"]  # both keys already recorded by the graph
    appr = {a["role"]: a["verdict"] for a in await db.list_approvals(jid) if a["stage"] == "exposure"}
    assert appr == {"sec-compliance": "PASS", "exec-ceo-strategist": "PASS"}
    assert env.dep.exposed == []  # nothing public before the owner's click
    await owner(env, jid)
    job = await db.get_job(jid)
    assert env.dep.exposed == [1]
    assert job["preview"]["tier"] == 1 and job["preview"]["url"].startswith("https://p1")
    assert job["pending"][0]["stage"] == "handoff"


async def test_after_n_owner_clicks_the_two_keys_alone_expose_a_gated_preview(env):
    for _ in range(3):
        await env.db.bump_counter("tier1_owner_clicks")
    jid = await start(env, tier=1)
    await owner(env, jid)  # verify
    job = await db.get_job(jid)
    assert job["pending"][0]["stage"] == "handoff"  # exposure passed without the owner
    assert env.dep.exposed == [1]


async def test_tier2_always_needs_the_owner(env):
    for _ in range(10):
        await env.db.bump_counter("tier1_owner_clicks")
    jid = await start(env, tier=2)
    await owner(env, jid)
    job = await db.get_job(jid)
    assert job["pending"][0] == {"stage": "exposure", "roles": ["owner"], "needsOwner": True}


async def test_missing_auth_layer_blocks_exposure_before_any_route_exists(env):
    env.dep.auth_ok = False
    jid = await start(env, tier=1)
    await owner(env, jid)  # verify
    job = await db.get_job(jid)
    assert job["status"] == "parked" and "exposure" in job["parkReason"]
    assert env.dep.exposed == []  # no public route was ever created


async def test_a_public_route_that_answers_without_credentials_is_taken_down(env):
    env.dep.probe_ok = False  # the route is up but does not refuse anonymous requests
    jid = await start(env, tier=1)
    await owner(env, jid)  # verify
    await owner(env, jid)  # exposure: the owner's click; the route is applied and probed
    job = await db.get_job(jid)
    assert env.dep.exposed == [1] and env.dep.stopped == 1
    assert job["status"] == "parked" and "taken down" in job["parkReason"]
    assert job["preview"]["url"] is None and job["preview"]["stopped"] is True and job["tier"] == 0


# ---------- review rules ----------

async def test_a_lead_fail_sends_the_stage_back_with_reasons_then_passes(env):
    env.script.review_verdicts["scope"] = ["FAIL", "PASS"]
    jid = await start(env)
    job = await run_to_end(env, jid)
    assert job["status"] == "done"
    assert job["stages"]["scope"]["attempts"] == 2


async def test_repeated_fails_park_the_job_and_the_owner_can_retry_or_kill(env):
    env.script.review_verdicts["scope"] = ["FAIL", "FAIL", "FAIL"]
    jid = await start(env)
    await owner(env, jid)  # verify
    job = await db.get_job(jid)
    assert job["status"] == "parked" and "scope" in job["parkReason"]
    env.script.review_verdicts["security"] = ["FAIL", "FAIL", "FAIL"]
    await env.graph.ainvoke(Command(resume={"action": "retry", "note": "try again"}), config=thread(jid))
    job = await db.get_job(jid)
    assert job["stages"]["scope"]["state"] == "approved"  # the retry fixed scope ...
    assert job["status"] == "parked" and "security" in job["parkReason"]  # ... and security then failed review
    await jobs.touch(jid, status="killed")
    await env.graph.ainvoke(Command(resume={"action": "kill"}), config=thread(jid))
    assert (await db.get_job(jid))["status"] == "killed"


async def test_pass_without_cited_evidence_is_a_fail(env):
    env.script.review_verdicts["scope"] = ["NOCITE", "PASS"]
    jid = await start(env)
    await run_to_end(env, jid)
    job = await db.get_job(jid)
    assert job["stages"]["scope"]["attempts"] == 2


async def test_a_cite_that_is_not_evidence_of_this_stage_does_not_count(env):
    env.script.review_verdicts["scope"] = ["PREFIX", "PASS"]  # a bare job-id prefix names no evidence
    jid = await start(env)
    await run_to_end(env, jid)
    job = await db.get_job(jid)
    assert job["stages"]["scope"]["attempts"] == 2
    passed = [a for a in await db.list_approvals(jid) if a["stage"] == "scope" and a["verdict"] == "PASS"]
    assert passed and all(c.startswith(f"{jid}:scope:") for a in passed for c in a["evidence"])  # labels resolved to real ids


REGISTRY_DOWN = [{"name": "dependencies install", "ok": False, "detail": "npm ERR! code ECONNRESET\n[registry unreachable]"}]
GREEN = [{"name": "unit tests pass (npm test)", "ok": True, "detail": "12 passed"}]


async def test_a_registry_outage_reruns_only_the_checks_and_uses_no_review_round(env, monkeypatch):
    monkeypatch.setitem(env.cfg.worker, "recheck_pause_s", 0)
    env.worker.checks = [REGISTRY_DOWN, GREEN]
    env.worker.recheck_results = [GREEN]
    jid = await start(env)
    job = await run_to_end(env, jid)
    assert env.worker.runs == 1 and env.worker.rechecks == 1  # the agent ran once; only the checks ran again
    assert job["stages"]["build"]["attempts"] == 1 and job["status"] != "parked"
    assert any("re-running the checks only" in e["text"] for e in job["events"])


async def test_a_registry_outage_that_lasts_parks_the_build_without_failing_a_review(env, monkeypatch):
    monkeypatch.setitem(env.cfg.worker, "recheck_pause_s", 0)
    env.worker.checks = [REGISTRY_DOWN]
    env.worker.recheck_results = [REGISTRY_DOWN, REGISTRY_DOWN]
    jid = await start(env)
    await owner(env, jid)  # verify -> scope -> build
    job = await db.get_job(jid)
    assert job["status"] == "parked" and "registry is unreachable" in job["parkReason"]
    assert env.worker.runs == 1 and env.worker.rechecks == 2
    assert not [a for a in await db.list_approvals(jid) if a["stage"] == "build"]  # no lead was asked to fail it
    assert job["costs"]["tokens"] >= 1000  # the agent run is still paid for


async def test_failed_security_check_fails_without_asking_a_model(env):
    env.checks.ok = False
    before = len(env.script.calls)
    jid = await start(env)
    await owner(env, jid)  # verify -> ... -> security fails
    job = await db.get_job(jid)
    assert job["status"] == "parked" and "security" in job["parkReason"]
    reviews = [c for c in env.script.calls if c == "lead_review"]
    assert len(reviews) == 3  # verify, scope, build were reviewed by the model; security never reaches it
    assert env.dep.deployed == 0


async def test_a_review_by_the_wrong_model_is_void(env):
    env.script.mismatch = True
    jid = await start(env)
    job = await db.get_job(jid)  # the very first review (verify) is void three times -> parked
    assert job["status"] == "parked" and "verify" in job["parkReason"]
    assert "review void" in job["parkReason"] and "other-model" in job["parkReason"]


async def test_an_unfinished_build_fails_the_stage(env):
    env.worker.exit_state = "timeout"
    jid = await start(env)
    await owner(env, jid)
    job = await db.get_job(jid)
    assert job["status"] == "parked" and "build" in job["parkReason"]


async def test_a_swapped_builder_model_fails_the_stage(env):
    env.worker.models = ["some-free-model"]
    jid = await start(env)
    await owner(env, jid)
    job = await db.get_job(jid)
    assert job["status"] == "parked" and "build" in job["parkReason"]


async def test_incomplete_brief_parks_before_any_model_call(env):
    bad = {**GOOD_BRIEF, "deposit_ref": ""}
    jid = await start(env, brief=bad)
    job = await db.get_job(jid)
    assert job["status"] == "parked" and "deposit" in job["parkReason"]
    assert env.script.calls == []


async def test_budget_cap_parks_the_job(env, monkeypatch):
    monkeypatch.setitem(env.cfg.budget, "lanes", {"build": {"usd": 0.005, "tokens": 0}})  # the fake builder reports $0.01
    jid = await start(env)
    await owner(env, jid)
    job = await db.get_job(jid)
    assert job["status"] == "parked" and "budget" in job["parkReason"]


async def test_token_cap_parks_the_job_even_when_the_models_are_free(env, monkeypatch):
    monkeypatch.setitem(env.cfg.budget, "lanes", {"build": {"usd": 100.0, "tokens": 50}})
    jid = await start(env)
    await owner(env, jid)
    job = await db.get_job(jid)
    assert job["status"] == "parked" and "token" in job["parkReason"]


async def test_router_outage_parks_with_a_clear_reason_instead_of_failing_review_loops(env, monkeypatch):
    class APIConnectionError(Exception):
        pass

    async def down(*a, **k):
        raise APIConnectionError("connection refused")
    monkeypatch.setattr(env.script, "chat_json", down)
    set_deps(Deps(chat_json=down, worker=env.worker, deployer=env.dep, checks=env.checks))
    jid = await start(env)
    job = await db.get_job(jid)
    assert job["status"] == "parked" and "9router" in job["parkReason"]


def test_build_cost_comes_from_tokens_and_the_price_table_not_the_workers_own_figure():
    from app.pipeline.stages import worker_usd
    res = {"tokens_in": 1_000_000, "tokens_out": 100_000, "tokens_cached": 10_000_000, "usd": 99.0}
    assert worker_usd("cc/claude-haiku-4-5-20251001", res) == 1.0 + 0.5 + 1.0
    assert worker_usd("cc/claude-haiku-4-5-20251001", {"usd": 0.25}) == 0.25


async def test_jobs_carry_only_their_lanes_stages_and_an_hours_deadline(env):
    job = jobs.new_job("client", "t", dict(GOOD_BRIEF))
    assert "research" not in job["stages"] and job["lane"] == "build"
    assert job["deadlineAt"] - job["createdAt"] == 7 * 3600 * 1000
    v = jobs.new_job("own", "t", {"title": "t"}, lane="validate")
    assert list(v["stages"]) == ["intake", "research"]


async def test_approvals_are_idempotent(env):
    jid = await start(env)
    assert await db.record_approval(jid, "verify", "owner", "PASS", "", [], "owner") is True
    assert await db.record_approval(jid, "verify", "owner", "PASS", "", [], "owner") is False


# ---------- HTTP ----------

@pytest.fixture
def api(env, isolated_brain, monkeypatch):
    from contextlib import asynccontextmanager
    from app.main import app
    from conftest import OFFICE_HEADERS

    @asynccontextmanager
    async def lifespan(_):
        yield
    monkeypatch.setattr(app.router, "lifespan_context", lifespan)
    with TestClient(app, headers=OFFICE_HEADERS) as c:
        yield c


def wait_status(api, jid, status, timeout=8.0):
    import time
    end = time.time() + timeout
    while time.time() < end:
        j = api.get(f"/api/jobs/{jid}").json()
        if j["status"] == status:
            return j
        time.sleep(0.03)
    raise AssertionError(f"never {status}: {j['status']} {j['pending']}")


def test_http_flow_owner_gates_counter_and_kill(api, env):
    r = api.post("/api/jobs", json={**GOOD_BRIEF, "requestedTier": 1})
    assert r.status_code == 200
    jid = r.json()["id"]
    job = wait_status(api, jid, "waiting")
    assert job["pending"][0]["stage"] == "verify"

    assert api.post(f"/api/jobs/{jid}/gates/scope", json={"verdict": "PASS"}).status_code == 409  # not waiting there
    assert api.post(f"/api/jobs/{jid}/gates/verify", json={"verdict": "MAYBE"}).status_code == 400
    assert api.post(f"/api/jobs/{jid}/gates/verify", json={"verdict": "PASS"}).status_code == 200
    job = wait_status(api, jid, "waiting")
    import time
    end = time.time() + 5
    while job["pending"] and job["pending"][0]["stage"] != "exposure" and time.time() < end:
        time.sleep(0.03)
        job = api.get(f"/api/jobs/{jid}").json()
    assert job["pending"][0]["stage"] == "exposure"
    assert api.post(f"/api/jobs/{jid}/gates/exposure", json={"verdict": "PASS"}).status_code == 200
    assert api.post(f"/api/jobs/{jid}/gates/exposure", json={"verdict": "PASS"}).status_code in (409, 200)
    assert env.db.counters.get("tier1_owner_clicks") == 1  # counted once

    job = api.get(f"/api/jobs/{jid}").json()
    assert {a["role"] for a in job["approvals"] if a["stage"] == "exposure"} >= {"sec-compliance", "exec-ceo-strategist", "owner"}
    assert any(e["kind"] == "probe" for e in job["evidence"])

    killed = api.post(f"/api/jobs/{jid}/kill").json()
    assert killed["status"] == "killed" and env.dep.stopped == 1


def test_http_create_validation(api):
    assert api.post("/api/jobs", json={"kind": "own", "lane": "build", "title": "x"}).status_code == 400  # needs fromJob
    assert api.post("/api/jobs", json={"title": "x", "lane": "ship-it"}).status_code == 400
    assert api.post("/api/jobs", json={"description": "no title"}).status_code == 400
    assert api.post("/api/jobs", json={"title": "x", "requestedTier": 7}).status_code == 400
    assert api.get("/api/jobs/missing").status_code == 404


async def test_expired_previews_are_taken_down(env):
    from app.pipeline.janitor import expire_previews
    jid = await start(env, tier=1)
    await owner(env, jid)       # verify
    await owner(env, jid)       # exposure (owner click)
    job = await db.get_job(jid)
    assert job["preview"]["tier"] == 1
    assert await expire_previews(now_ms=job["preview"]["expiresAt"] - 1) == 0
    assert await expire_previews(now_ms=job["preview"]["expiresAt"] + 1) == 1
    job = await db.get_job(jid)
    assert job["preview"]["stopped"] is True and job["preview"]["url"] is None and env.dep.stopped == 1
    assert await expire_previews(now_ms=job["preview"]["expiresAt"] + 2) == 0  # only once


def test_stage_order_comes_from_config_not_from_storage_order():
    cfg_names = [s["name"] for s in load_config().pipeline["stages"] if s["name"] != "research"]  # build lane
    job = jobs.new_job("client", "T", {"title": "T"})
    job["stages"] = dict(reversed(list(job["stages"].items())))  # what a JSONB round trip may do
    assert [s["name"] for s in jobs.public(job)["stages"]] == cfg_names


async def test_a_failing_test_run_fails_the_build_and_the_retry_sees_the_output(env):
    red = [{"name": "unit tests pass (npm test)", "ok": False, "detail": "FAIL src/order.test.ts: expected 3 got 2"}]
    green = [{"name": "unit tests pass (npm test)", "ok": True, "detail": "12 passed"}]
    env.worker.checks = [red, green]
    jid = await start(env)
    await owner(env, jid)
    assert env.worker.runs == 2
    assert "expected 3 got 2" in env.worker.briefs[1]["feedback"]
    ev = [e for e in await db.list_evidence(jid) if e["stage"] == "build" and e["kind"] == "check"]
    assert any(e["ok"] is False for e in ev) and any(e["ok"] is True for e in ev)


async def test_a_worker_without_check_results_cannot_pass_the_build(env):
    env.worker.checks = None
    jid = await start(env)
    await owner(env, jid)
    job = await db.get_job(jid)
    assert job["status"] == "parked" and job["stage"] == "build"


async def test_green_checks_make_a_lead_fail_on_build_advisory(env):
    env.script.review_verdicts["build"] = ["FAIL"]
    jid = await start(env)
    job = await run_to_end(env, jid)
    assert job["status"] == "done"
    assert job["stages"]["build"]["attempts"] == 1
