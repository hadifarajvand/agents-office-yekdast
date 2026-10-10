"""Tests against a real PostgreSQL. Skipped unless AO_TEST_DATABASE_URL is set, e.g.
    AO_TEST_DATABASE_URL=postgresql://office:office@localhost:5432/office_test pytest

Covers what fakes cannot: the SQL in app/db.py and migrations, and LangGraph's
AsyncPostgresSaver keeping a paused task across a process restart (a brand-new pool,
saver and compiled graph resume the same thread exactly once).
"""
from __future__ import annotations

import os

import psycopg
import pytest

URL = os.environ.get("AO_TEST_DATABASE_URL")
pytestmark = pytest.mark.skipif(not URL, reason="AO_TEST_DATABASE_URL not set")


@pytest.fixture
async def pool():
    from app import db
    # fresh schema each test
    async with await psycopg.AsyncConnection.connect(URL, autocommit=True) as c:
        await c.execute("DROP SCHEMA public CASCADE; CREATE SCHEMA public;")
    db._pool = None
    p = await db.open_pool(URL)
    yield p
    await db.close_pool()


async def test_migrations_apply_once(pool):
    from app import db
    assert await db.migrate(pool) == []  # already applied by open_pool


async def test_task_roundtrip_and_atomic_claim(pool):
    from app import db
    await db.save_task({"id": "t1", "state": "waiting", "title": "x", "createdAt": 1})
    assert (await db.get_task("t1"))["title"] == "x"
    first = await db.claim_task("t1", "waiting", "doing")
    second = await db.claim_task("t1", "waiting", "doing")
    assert first["state"] == "doing" and second is None
    await db.save_task({**first, "state": "doing"})
    assert await db.fail_interrupted_tasks() == 1
    assert (await db.get_task("t1"))["error"] is True
    await db.delete_task("t1")
    assert await db.list_tasks() == []


async def test_routine_state_upsert_and_slot_claim(pool):
    from app import db
    await db.save_routine_state({"a": {"runs": 1}, "b": {"runs": 2}})
    await db.save_routine_state({"a": {"runs": 3}})
    assert await db.load_routine_state() == {"a": {"runs": 3}}
    assert await db.claim_routine_slot("a", 1000) is True
    assert await db.claim_routine_slot("a", 1000) is False


async def test_jobs_approvals_evidence_costs(pool):
    from app import db
    await db.save_job({"id": "j1", "kind": "client", "title": "Site", "stage": "intake", "status": "running"})
    assert (await db.get_job("j1"))["title"] == "Site"
    assert await db.record_approval("j1", "verify", "exec-ceo-strategist", "PASS", "ok", ["e1"], "exec-ceo-strategist") is True
    assert await db.record_approval("j1", "verify", "exec-ceo-strategist", "PASS", "ok", ["e1"], "exec-ceo-strategist") is False
    assert len(await db.list_approvals("j1")) == 1
    await db.clear_approvals("j1", "verify")
    assert await db.list_approvals("j1") == []
    eid = await db.add_evidence("j1", "security", "check", "secret scan", True, {"hits": 0}, evidence_id="ev1")
    await db.add_evidence("j1", "security", "check", "secret scan", False, {"hits": 1}, evidence_id="ev1")
    ev = await db.list_evidence("j1")
    assert eid == "ev1" and len(ev) == 1 and ev[0]["ok"] is False
    await db.record_cost("task:x", "oc/mimo-v2.5-free", "glm-5", 10, 5, 0.0)
    assert (await db.usage_window())["tokens"] == 15
    assert await db.bump_counter("tier1_owner_clicks") == 1
    assert await db.counter("tier1_owner_clicks") == 1
    await db.audit("sec-compliance", "secdata", "dokploy", "application-deploy", "previews/app", True)


async def test_paused_task_survives_restart_and_resumes_once(pool, monkeypatch):
    from langgraph.checkpoint.postgres.aio import AsyncPostgresSaver
    from psycopg_pool import AsyncConnectionPool

    from app import db
    from app.graph import engine
    from app.roster import defaults

    calls = []

    async def fake_ask_with_tools(messages, tools, **kw):
        user = next(m["content"] for m in messages if m["role"] == "user")
        calls.append(user)
        return {"content": "SENT" if "owner approved" in user else "DRAFT", "tool_calls": []}

    monkeypatch.setattr(engine, "ask_with_tools", fake_ask_with_tools)
    agent = next(a for a in defaults() if a.id == "invo")
    skills = type("S", (), {"names": lambda self, a: [], "prompt_text": lambda self, a: ""})()
    task = {"id": "restart-1", "thread": "restart-1-1", "dept": "fin", "title": "Email", "text": "email the client"}

    saver = AsyncPostgresSaver(pool)
    await saver.setup()
    engine.compile_graph(checkpointer=saver)
    from pathlib import Path
    out = await engine.run_task(task, None, "draft", agent, defaults(), skills, Path("/tmp"), "haiku", None)
    assert out["paused"] is True and out["draft"] == "DRAFT"

    # "Restart": drop the pool and graph, build new ones against the same database.
    await db.close_pool()
    pool2 = AsyncConnectionPool(URL, kwargs=db.pool_kwargs(), open=False)
    await pool2.open()
    try:
        engine.compile_graph(checkpointer=AsyncPostgresSaver(pool2))
        assert await engine.is_paused("restart-1-1") is True
        res = await engine.resume_task("restart-1-1", "approve", None, skills, agent)
        assert res["result"] == "SENT" and res["paused"] is False
        assert sum(1 for c in calls if "owner approved" in c) == 1
        assert await engine.is_paused("restart-1-1") is False
    finally:
        engine.compile_graph(checkpointer=None)
        await pool2.close()


async def test_pipeline_job_waiting_for_the_owner_survives_a_restart(pool, tmp_path, monkeypatch):
    from langgraph.checkpoint.postgres.aio import AsyncPostgresSaver
    from langgraph.types import Command
    from psycopg_pool import AsyncConnectionPool

    from app import db
    from app.config import load_config
    from app.pipeline import jobs
    from app.pipeline.api import thread
    from app.pipeline.graph import compile_pipeline
    from app.pipeline.ports import Deps, set_deps
    from test_pipeline import GOOD_BRIEF, FakeChecks, FakeDeployer, FakeWorker, Script

    monkeypatch.setitem(load_config().sandbox, "jobs_dir", str(tmp_path / "jobs"))
    from app.pipeline import exposure as exp
    monkeypatch.setitem(load_config().pipeline, "live_departments", list(exp.ALL_DEPTS))
    script, worker, dep = Script(), FakeWorker(), FakeDeployer()
    set_deps(Deps(chat_json=script.chat_json, worker=worker, deployer=dep, checks=FakeChecks(), jobs_dir=tmp_path))
    saver = AsyncPostgresSaver(pool)
    await saver.setup()
    graph = compile_pipeline(saver)
    job = jobs.new_job("client", "Bakery", dict(GOOD_BRIEF))
    await db.save_job(job)
    state = {"job_id": job["id"], "kind": "client", "brief": dict(GOOD_BRIEF), "requested_tier": 0,
             "loops": {}, "feedback": "", "route": ""}
    await graph.ainvoke(state, config=thread(job["id"]))
    assert (await db.get_job(job["id"]))["pending"][0]["stage"] == "verify"
    await db.record_approval(job["id"], "verify", "owner", "PASS", "", [], "owner")

    # "Restart": a new pool, saver and compiled graph over the same database.
    await db.close_pool()
    pool2 = AsyncConnectionPool(URL, kwargs=db.pool_kwargs(), open=False)
    await pool2.open()
    try:
        db._pool = pool2
        graph2 = compile_pipeline(AsyncPostgresSaver(pool2))
        await graph2.ainvoke(Command(resume={"owner": "PASS"}), config=thread(job["id"]))
        j = await db.get_job(job["id"])
        assert j["pending"][0]["stage"] == "handoff" and j["stages"]["verify"]["state"] == "approved"
        assert worker.runs == 1 and dep.deployed == 1  # the work after verify ran exactly once
    finally:
        db._pool = None
        await pool2.close()
        set_deps(None)


async def test_brain_full_text_index_ranks_and_replaces(pool, tmp_path):
    from app import brain
    (tmp_path / "offer.md").write_text("# Offer\nStarter bakery ordering site 1500 USD")
    (tmp_path / "lunch.md").write_text("# Lunch\nSandwich menu")
    brain._index_sig["sig"] = None
    hits = await brain.search(tmp_path, "price of a bakery ordering site", k=2)
    assert hits[0]["note"] == "offer" and all(h["note"] != "lunch" for h in hits)
    (tmp_path / "offer.md").write_text("# Offer\nnothing relevant now")
    assert await brain.reindex(tmp_path) > 0
    assert await brain.search(tmp_path, "bakery") == []


async def test_spawn_and_consult_evidence_round_trips_through_jsonb(pool, monkeypatch):
    """The fakes accept any body; JSONB does not. Spawn and consult once wrote a bare string and broke every read."""
    from app import db
    from app.pipeline import spawn as sp

    async def fake_ask(system, user, **kw):
        return "answer text"
    monkeypatch.setattr(sp, "ask", fake_ask)
    await db.save_job({"id": "jx", "kind": "client", "title": "x", "stage": "intake", "status": "running"})
    await sp.spawn("exec-vp-engineering", "eng-api-designer", "name the endpoints", job_id="jx", stage="scope")
    await sp.consult("exec-ceo-strategist", "exec-vp-engineering", "how long?", job_id="jx", stage="verify")
    ev = await db.list_evidence("jx")
    assert {e["kind"] for e in ev} == {"spawn", "consult"} and all(e["body"]["text"] == "answer text" for e in ev)


async def test_a_killed_job_stays_killed_when_a_stale_copy_is_saved(pool):
    """The graph reads a job, the owner kills it, then the graph writes its stale copy back."""
    from app import db
    from app.pipeline import jobs as jobsmod
    job = jobsmod.new_job("client", "race", {"title": "race"})
    await db.save_job(job)
    stale = await db.get_job(job["id"])
    await jobsmod.touch(job["id"], status="killed", pending=[])
    stale.update(status="waiting", stage="verify")
    await db.save_job(stale)
    back = await db.get_job(job["id"])
    assert back["status"] == "killed" and back["stage"] == "verify"
    assert [j["status"] for j in await db.list_jobs() if j["id"] == job["id"]] == ["killed"]
