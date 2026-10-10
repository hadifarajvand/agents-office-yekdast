"""Contract tests for the /api/* routes the frontend calls (src/tasks.js, src/main.js,
src/connectors.js). The model layer and Postgres are faked (tests/fakes.py), so no
router or database is needed. Key behaviours:
  - /run and /revise block; a task that needs the owner's OK comes back "waiting"
    with a draft, otherwise "done" with a result;
  - /approve and /reject acknowledge at once and finish in the background, and the
    waiting -> doing move is atomic (a second click is refused);
  - every state-changing request needs the X-AO-Client header.
"""
from __future__ import annotations

import time
from contextlib import asynccontextmanager

import pytest
from fastapi.testclient import TestClient
from langgraph.checkpoint.memory import InMemorySaver

from app.graph import engine
from app.main import app
from conftest import OFFICE_HEADERS


@pytest.fixture
def router_says(monkeypatch):
    """Control what the routing model decides; default: needs the owner's OK."""
    decision = {"needs_ok": True}

    async def fake_route_json(system, user):
        return {"agent": None, "title": "Mocked task", "plan": ["step1"], "eta_minutes": 5,
                "why": "mocked routing", "needs_ok": decision["needs_ok"]}

    async def fake_ask(system, user, model_key=None, **kw):
        return "mocked agent output"

    async def fake_ask_with_tools(messages, tools, model_key=None, **kw):
        user = next((m["content"] for m in messages if m["role"] == "user"), "")
        if "owner approved" in user:
            return {"content": "sent after OK", "tool_calls": []}
        return {"content": "mocked agent output", "tool_calls": []}

    monkeypatch.setattr(engine, "ask_haiku_json", fake_route_json)
    monkeypatch.setattr(engine, "ask", fake_ask)
    monkeypatch.setattr(engine, "ask_with_tools", fake_ask_with_tools)
    return decision


@asynccontextmanager
async def _no_db_lifespan(_app):
    yield


@pytest.fixture
def client(fake_db, router_says, isolated_brain, monkeypatch):
    # Keep one event loop alive across requests (background approvals run on it), but
    # skip the real lifespan: no Postgres pool, no routine ticker.
    monkeypatch.setattr(app.router, "lifespan_context", _no_db_lifespan)
    engine.compile_graph(checkpointer=InMemorySaver())
    with TestClient(app, headers=OFFICE_HEADERS) as c:
        yield c
    engine.compile_graph(checkpointer=None)


def wait_for(fake_db, task_id, state, timeout=5.0):
    end = time.time() + timeout
    while time.time() < end:
        t = fake_db.tasks.get(task_id)
        if t and t.get("state") == state:
            return t
        time.sleep(0.02)
    raise AssertionError(f"task {task_id} never reached {state}: {fake_db.tasks.get(task_id)}")


# ---------- request hygiene ----------

def test_mutating_request_without_client_header_is_refused(client):
    r = client.post("/api/tasks", json={"dept": "fin", "text": "x"}, headers={"X-AO-Client": ""})
    assert r.status_code == 403


def test_text_plain_body_is_refused(client):
    r = client.post("/api/tasks", content="dept=fin", headers={"content-type": "text/plain"})
    assert r.status_code == 415


def test_foreign_origin_is_refused(client):
    r = client.get("/api/health", headers={"origin": "https://evil.example"})
    assert r.status_code == 403


def test_foreign_host_is_refused(client):
    r = client.get("/api/health", headers={"host": "evil.example"})
    assert r.status_code == 403


def test_api_token_required_when_configured(client, monkeypatch):
    monkeypatch.setenv("AO_API_TOKEN", "s3cret")
    assert client.get("/api/health").status_code == 401
    assert client.get("/api/health", headers={"X-AO-Token": "s3cret"}).status_code == 200


def test_page_carries_token_meta_when_configured(client, monkeypatch, tmp_path):
    from app import main
    page = tmp_path / "page.html"
    page.write_text("<html><head></head><body></body></html>")
    monkeypatch.setattr(main, "HTML", page)
    monkeypatch.setenv("AO_API_TOKEN", "s3cret")
    assert '<meta name="ao-token" content="s3cret">' in client.get("/").text


def test_non_object_json_body_is_a_400(client):
    r = client.post("/api/tasks", json=["not", "an", "object"])
    assert r.status_code == 400


# ---------- read-only info routes ----------

def test_health_shape(client):
    body = client.get("/api/health").json()
    for key in ("ok", "version", "backend", "model", "models", "depts", "agents", "agentCount",
                "routines", "roster", "skills", "tools", "mcp", "pipeline", "roles"):
        assert key in body
    assert isinstance(body["agents"], list) and body["agentCount"] == len(body["agents"]) == 17
    assert [s["name"] for s in body["pipeline"]["stages"]][:2] == ["intake", "verify"]


def test_agents_shape_and_approval_scopes(client):
    agents = client.get("/api/agents").json()["agents"]
    first = agents[0]
    for key in ("id", "department", "lead", "name", "role", "does", "tools", "approves"):
        assert key in first
    by_id = {a["id"]: a for a in agents}
    assert "exposure" in by_id["sec-compliance"]["approves"] and "exposure" in by_id["exec-ceo-strategist"]["approves"]
    assert "exposure" not in by_id["exec-vp-engineering"]["approves"]  # the builder never approves exposure
    assert all(not a["approves"] for a in agents if not a["lead"])


def test_brain_has_graph_shape(client):
    body = client.get("/api/brain").json()
    for key in ("notes", "nodes", "links", "floor"):
        assert key in body


def test_usage_is_the_office_count_in_ms(client):
    body = client.get("/api/usage").json()
    assert body["source"] == "office"
    assert body["window"]["resetsAt"] > 1e12  # milliseconds, not seconds


# ---------- tasks ----------

def test_create_task_validates(client):
    assert client.post("/api/tasks", json={"dept": "fin"}).status_code == 400
    assert client.post("/api/tasks", json={"dept": "nope", "text": "x"}).status_code == 400
    assert client.post("/api/tasks", json={"dept": "fin", "text": "x", "model": "sonnet-evil"}).status_code == 400


def test_create_task_sets_frontend_fields(client):
    task = client.post("/api/tasks", json={"dept": "fin", "text": "chase overdue invoices"}).json()
    for key in ("id", "dept", "text", "state", "agent", "title", "plan", "needsOk", "addedAt"):
        assert key in task
    assert task["state"] == "next" and task["addedAt"] > 1e12


def test_run_without_ok_blocks_and_returns_done(client, router_says):
    router_says["needs_ok"] = False
    created = client.post("/api/tasks", json={"dept": "fin", "text": "list overdue invoices"}).json()
    task = client.post(f"/api/tasks/{created['id']}/run").json()
    assert task["state"] == "done"
    assert task["result"] == "mocked agent output"
    assert task["startedAt"] and task["doneAt"]


def test_run_that_needs_ok_returns_waiting_with_draft(client):
    created = client.post("/api/tasks", json={"dept": "fin", "text": "email the client"}).json()
    task = client.post(f"/api/tasks/{created['id']}/run").json()
    assert task["state"] == "waiting"
    assert task["draft"] == "mocked agent output"
    assert task["waitingAt"] and task["ask"]


def test_approve_finishes_in_background_and_marks_approved(client, fake_db):
    created = client.post("/api/tasks", json={"dept": "fin", "text": "email the client"}).json()
    client.post(f"/api/tasks/{created['id']}/run")
    r = client.post(f"/api/tasks/{created['id']}/approve")
    assert r.json() == {"ok": True, "id": created["id"], "state": "doing"}
    t = wait_for(fake_db, created["id"], "done")
    assert t["approved"] is True and t["result"] == "sent after OK"


def test_second_approve_is_refused(client, fake_db):
    created = client.post("/api/tasks", json={"dept": "fin", "text": "email the client"}).json()
    client.post(f"/api/tasks/{created['id']}/run")
    assert client.post(f"/api/tasks/{created['id']}/approve").status_code == 200
    assert client.post(f"/api/tasks/{created['id']}/approve").status_code == 400


def test_reject_redrafts_and_waits_again(client, fake_db):
    created = client.post("/api/tasks", json={"dept": "fin", "text": "email the client"}).json()
    client.post(f"/api/tasks/{created['id']}/run")
    r = client.post(f"/api/tasks/{created['id']}/reject", json={"feedback": "shorter"})
    assert r.status_code == 200
    time.sleep(0.05)
    t = wait_for(fake_db, created["id"], "waiting")
    assert t.get("revised") is True


def test_approve_requires_waiting_state(client):
    created = client.post("/api/tasks", json={"dept": "fin", "text": "x"}).json()
    assert client.post(f"/api/tasks/{created['id']}/approve").status_code == 400


def test_run_unknown_task_404(client):
    assert client.post("/api/tasks/not-a-real-id/run").status_code == 404


def test_delete_task(client, fake_db):
    created = client.post("/api/tasks", json={"dept": "fin", "text": "x"}).json()
    assert client.delete(f"/api/tasks/{created['id']}").json() == {"ok": True}
    assert created["id"] not in fake_db.tasks


# ---------- routines ----------

def test_list_routines_shape(client):
    body = client.get("/api/routines").json()
    for key in ("routines", "depts", "path", "problems"):
        assert key in body


def test_create_routine_validates(client):
    when = {"kind": "daily", "at": "09:00"}
    assert client.post("/api/routines", json={"dept": "nope", "text": "x", "when": when}).status_code == 400
    assert client.post("/api/routines", json={"dept": "frontend", "text": "x", "when": when}).status_code == 400
    assert client.post("/api/routines", json={"dept": "fin", "text": "", "when": when}).status_code == 400
    assert client.post("/api/routines", json={"dept": "fin", "text": "chase overdue invoices"}).status_code == 400


def test_routine_roundtrip(client, fake_db):
    created = client.post("/api/routines", json={
        "dept": "fin", "text": "list overdue invoices", "when": {"kind": "weekly", "days": [1], "at": "09:00"},
        "model": "haiku",
    })
    assert created.status_code == 200, created.json()
    routine = created.json()["routine"]
    assert routine["desc"] and routine["nextAt"]
    rid = routine["id"]
    listed = client.get("/api/routines").json()["routines"]
    assert any(r["id"] == rid and r.get("desc") for r in listed)

    run = client.post(f"/api/routines/{rid}/run").json()
    assert run["ok"] and run["task"]["routine"] == rid

    assert client.post(f"/api/routines/{rid}/pause").status_code == 200
    assert next(r for r in client.get("/api/routines").json()["routines"] if r["id"] == rid)["paused"] is True
    assert client.post(f"/api/routines/{rid}/resume").status_code == 200
    assert client.post(f"/api/routines/{rid}", json={"title": "Renamed"}).status_code == 200
    assert next(r for r in client.get("/api/routines").json()["routines"] if r["id"] == rid)["title"] == "Renamed"
    assert client.post(f"/api/routines/{rid}", json={"when": {"kind": "nonsense"}}).status_code == 400
    assert client.delete(f"/api/routines/{rid}").status_code == 200
    assert not any(r["id"] == rid for r in client.get("/api/routines").json()["routines"])


def test_invalid_routine_lines_survive_a_save(client, isolated_brain):
    import json
    f = isolated_brain / "Agents Office" / "routines.json"
    f.parent.mkdir(parents=True, exist_ok=True)
    f.write_text(json.dumps({"routines": [{"id": "typo", "dept": "fin", "agent": "nobody", "text": "x",
                                           "when": {"kind": "daily", "at": "09:00"}}]}))
    client.post("/api/routines", json={"dept": "fin", "text": "list overdue invoices", "when": {"kind": "daily", "at": "10:00"}})
    ids = [r["id"] for r in json.loads(f.read_text())["routines"]]
    assert "typo" in ids and len(ids) == 2


def test_patch_unknown_routine_404(client):
    assert client.post("/api/routines/not-a-real-id", json={"title": "x"}).status_code == 404


# ---------- chat ----------

def test_chat_requires_known_agent(client):
    assert client.post("/api/chat", json={"agent": "not-a-real-agent", "text": "hi"}).status_code == 400


def test_chat_returns_reply(client):
    r = client.post("/api/chat", json={"agent": "invo", "text": "what's overdue?", "history": []})
    assert r.status_code == 200 and r.json()["reply"] == "mocked agent output"


def test_chat_ordinary_sentences_are_not_routine_commands(client):
    for text in ("schedule a call with the client", "running low on cash?", "delete the old draft"):
        assert client.post("/api/chat", json={"agent": "invo", "text": text}).json()["reply"] == "mocked agent output"


def test_chat_routine_commands(client):
    client.post("/api/routines", json={"dept": "fin", "text": "list overdue invoices", "when": {"kind": "daily", "at": "09:00"}})
    listed = client.post("/api/chat", json={"agent": "invo", "text": "routines"}).json()
    assert "list overdue invoices" in listed["reply"]
    paused = client.post("/api/chat", json={"agent": "invo", "text": "pause routine overdue invoices"}).json()
    assert "paused" in paused["reply"]


def test_unknown_route_404(client):
    assert client.get("/api/not-a-real-route").status_code == 404


def test_queue_off_by_default_and_arq_worker_importable(monkeypatch):
    from app import jobqueue
    monkeypatch.delenv("AO_QUEUE", raising=False)
    assert jobqueue.enabled() is False
    assert jobqueue.WorkerSettings.max_tries == 1 and jobqueue.WorkerSettings.functions


def test_once_routine_for_live_dept(client, fake_db):
    import time
    at = int((time.time() + 3600) * 1000)
    r = client.post("/api/routines", json={"dept": "engineering", "text": "check the build", "when": {"kind": "once", "atMs": at},
                                           "createdBy": "Dash"})
    assert r.status_code == 200, r.json()
    got = r.json()["routine"]
    assert got["createdBy"] == "Dash" and got["when"]["kind"] == "once"
    row = next(x for x in client.get("/api/routines").json()["routines"] if x["id"] == got["id"])
    assert row["needsYou"] is False
    assert client.post("/api/routines", json={"dept": "devops", "text": "x", "when": {"kind": "once"}}).status_code == 400


def test_job_stream_sends_the_view_then_ends_when_final(client, fake_db):
    import asyncio
    from app import db
    from app.pipeline import jobs
    job = jobs.new_job("client", "Stream me", {"title": "Stream me"}, requested_tier=0, lane="build")
    job["status"] = "done"
    asyncio.run(db.save_job(job))
    assert client.get("/api/jobs/nope/stream").status_code == 404
    r = client.get(f"/api/jobs/{job['id']}/stream")
    assert r.status_code == 200 and r.headers["content-type"].startswith("text/event-stream")
    assert r.text.startswith("data: ") and job["id"] in r.text


def test_archive_hides_a_job_but_keeps_it(client, fake_db):
    import asyncio
    from app import db
    from app.pipeline import jobs
    job = jobs.new_job("client", "Old test", {"title": "Old test"}, requested_tier=0, lane="build")
    job["status"] = "killed"
    asyncio.run(db.save_job(job))
    assert any(j["id"] == job["id"] for j in client.get("/api/jobs").json())
    assert client.post(f"/api/jobs/{job['id']}/archive", json={}, headers={"X-AO-Client": "office"}).status_code == 200
    assert not any(j["id"] == job["id"] for j in client.get("/api/jobs").json())
    assert any(j["id"] == job["id"] for j in client.get("/api/jobs?archived=true").json())
    assert client.get(f"/api/jobs/{job['id']}").status_code == 200


def test_queue_gives_each_job_one_driver(monkeypatch):
    import asyncio
    from app import jobqueue
    calls = []

    class Pool:
        async def enqueue_job(self, fn, *a, **kw):
            calls.append((fn, a, kw))
            return None if len(calls) > 1 else object()  # arq answers None for a job id it already holds

    monkeypatch.setattr(jobqueue, "_pool", Pool())
    assert asyncio.run(jobqueue.enqueue("j1", {"x": 1})) is True
    assert asyncio.run(jobqueue.enqueue("j1", {"x": 2})) is True  # duplicate: handled, never run in the API too
    assert {c[2]["_job_id"] for c in calls} == {"drive-j1"}


def test_worker_activity_reaches_the_api_buffer():
    from app import activity
    before = activity.since(0)["seq"]
    activity.ingest({"at": 1, "kind": "job-event", "text": "from the worker", "agent": None, "connector": None,
                     "job": "j", "stage": "build", "level": "info"})
    got = activity.since(before)
    assert [e["text"] for e in got["events"]] == ["from the worker"] and got["seq"] == before + 1


# ---------- tasks and routines in the worker (AO_QUEUE=1) ----------

@pytest.fixture
def queued(monkeypatch):
    """Queue on; the 'worker' is a callable the test controls. Records every enqueue_task call."""
    from app import jobqueue, main
    monkeypatch.setenv("AO_QUEUE", "1")
    seen, worker = [], {"drive": True}

    async def fake_enqueue(task_id, kind, feedback, approve, key):
        seen.append({"id": task_id, "kind": kind, "feedback": feedback, "approve": approve, "key": key})
        if worker["drive"]:
            main.spawn(main.drive_task(task_id, kind, feedback, approve))  # what the worker process does
        return True

    monkeypatch.setattr(jobqueue, "enqueue_task", fake_enqueue)
    return seen, worker


def test_queued_run_blocks_until_the_worker_settles_it(client, queued, router_says):
    seen, _ = queued
    router_says["needs_ok"] = False
    created = client.post("/api/tasks", json={"dept": "fin", "text": "list overdue invoices"}).json()
    task = client.post(f"/api/tasks/{created['id']}/run").json()
    assert task["state"] == "done" and task["result"] == "mocked agent output"
    assert [s["kind"] for s in seen] == ["run"] and seen[0]["id"] == created["id"]


def test_queued_approve_goes_to_the_worker_and_finishes(client, queued, fake_db):
    seen, _ = queued
    created = client.post("/api/tasks", json={"dept": "fin", "text": "email the client"}).json()
    assert client.post(f"/api/tasks/{created['id']}/run").json()["state"] == "waiting"
    r = client.post(f"/api/tasks/{created['id']}/approve")
    assert r.json()["state"] == "doing"
    t = wait_for(fake_db, created["id"], "done")
    assert t["approved"] is True and t["result"] == "sent after OK"
    assert [s["kind"] for s in seen] == ["run", "resume"] and seen[1]["approve"] is True


def test_queued_routine_run_is_left_to_the_worker(client, queued, fake_db):
    seen, worker = queued
    worker["drive"] = False  # the worker has not picked it up yet
    rid = client.post("/api/routines", json={
        "dept": "fin", "text": "list overdue invoices", "when": {"kind": "weekly", "days": [1], "at": "09:00"},
    }).json()["routine"]["id"]
    run = client.post(f"/api/routines/{rid}/run").json()
    tid = run["task"]["id"]
    assert [s["kind"] for s in seen] == ["routine"] and seen[0]["id"] == tid
    assert fake_db.tasks[tid]["state"] == "doing" and fake_db.tasks[tid]["thread"]  # nothing ran in the API
    assert fake_db.tasks[tid].get("result") is None


def test_worker_skips_a_task_that_was_settled_meanwhile(client, fake_db):
    import asyncio
    from app import main
    created = client.post("/api/tasks", json={"dept": "fin", "text": "list overdue invoices"}).json()
    asyncio.run(main.drive_task(created["id"], "run"))  # still "next": nobody started it
    assert fake_db.tasks[created["id"]]["state"] == "next"
    fake_db.tasks[created["id"]].update(state="done", error=True)  # marked failed by a restart
    asyncio.run(main.drive_task(created["id"], "routine"))
    assert fake_db.tasks[created["id"]]["state"] == "done" and fake_db.tasks[created["id"]]["error"] is True
