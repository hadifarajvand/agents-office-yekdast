"""Contract tests for every /api/* route in main.py, verified against src/tasks.js,
src/connectors.js and src/main.js (see .claude/plans/PLAN.md). Mocks the LLM (engine.ask / engine.ask_haiku_json) and Postgres (app.db) so no
network or database is needed. The two behaviors that matter most to the frontend's
6-second poll loop get explicit assertions: /run and /revise BLOCK and return a completed
task in one call; /approve and /reject ACK IMMEDIATELY and finish the work in the
background, so the caller sees "doing" long before the agent's result is ready.
"""
from __future__ import annotations

import asyncio
from pathlib import Path

import pytest
from fastapi.testclient import TestClient
from langgraph.checkpoint.memory import InMemorySaver

from app import db
from app.graph import engine
from app.main import app
from app.roster import defaults as default_agents


@pytest.fixture
def fake_store(monkeypatch):
    """Replace app.db's Postgres calls with an in-memory dict, keyed exactly like the
    real tasks/routine_state tables, so no route under test ever touches a real pool."""
    tasks: dict[str, dict] = {}
    routine_state: dict = {}

    async def list_tasks():
        return sorted(tasks.values(), key=lambda t: t.get("createdAt", 0))

    async def get_task(task_id):
        return tasks.get(task_id)

    async def save_task(task):
        tasks[task["id"]] = task

    async def delete_task(task_id):
        tasks.pop(task_id, None)

    async def load_routine_state():
        return dict(routine_state)

    async def save_routine_state(st):
        routine_state.clear()
        routine_state.update(st)

    monkeypatch.setattr(db, "list_tasks", list_tasks)
    monkeypatch.setattr(db, "get_task", get_task)
    monkeypatch.setattr(db, "save_task", save_task)
    monkeypatch.setattr(db, "delete_task", delete_task)
    monkeypatch.setattr(db, "load_routine_state", load_routine_state)
    monkeypatch.setattr(db, "save_routine_state", save_routine_state)
    return tasks


@pytest.fixture
def mock_llm(monkeypatch):
    """Mock both LLM entry points the engine uses, so /api/tasks (router), /run|/revise
    (specialist), and /api/chat never make a real Anthropic call."""
    async def fake_ask_haiku_json(system, user):
        return {"agent": None, "title": "Mocked task", "plan": ["step1"], "eta_minutes": 5,
                "why": "mocked routing", "needs_ok": True}

    async def fake_ask(system, user, model_key=None):
        return "mocked agent output"

    async def fake_ask_with_tools(messages, tools, model_key=None, max_tokens=4096):
        return {"content": "mocked agent output", "tool_calls": []}

    monkeypatch.setattr(engine, "ask_haiku_json", fake_ask_haiku_json)
    monkeypatch.setattr(engine, "ask", fake_ask)
    monkeypatch.setattr(engine, "ask_with_tools", fake_ask_with_tools)
    return {"ask_haiku_json": fake_ask_haiku_json, "ask": fake_ask, "ask_with_tools": fake_ask_with_tools}


@pytest.fixture
def graph_checkpointer():
    """Task 4's approve/reject flow resumes a graph paused at the "gate" node, which
    needs a real checkpointer to persist across calls — the module-level default has
    none. Compile with an in-memory one for the duration of each test, then restore."""
    engine.compile_graph(checkpointer=InMemorySaver())
    yield
    engine.compile_graph(checkpointer=None)


def _skills_stub():
    return type("S", (), {"names": lambda self, a: [], "prompt_text": lambda self, a: ""})()


def _seed_waiting_task(task: dict):
    """Mirrors the real route into "waiting": a routine firing with needsOk=True calls
    run_task(mode="draft"), which pauses the graph at "gate" rather than completing."""
    agent = next(a for a in default_agents() if a.department == task["dept"])
    # asyncio.run() closes its loop on exit, leaving this thread with no default
    # loop — fatal for a test that goes on to construct its own asyncio.Event().
    # Run on an explicit loop and install a fresh default one afterward instead.
    loop = asyncio.new_event_loop()
    try:
        loop.run_until_complete(engine.run_task(
            task, None, "draft", agent, default_agents(), _skills_stub(),
            brain_path=Path("."), office_model=None, office_effort=None,
        ))
    finally:
        loop.close()
        asyncio.set_event_loop(asyncio.new_event_loop())
    task["state"] = "waiting"


@pytest.fixture
def client(fake_store, mock_llm):
    # No `with` block: that would run FastAPI's startup event, which calls
    # db.get_pool() (real asyncpg) and spawns the routine-tick background loop —
    # neither is wanted in a contract test. Plain TestClient() dispatches requests
    # without the ASGI lifespan.
    return TestClient(app)


# ---------- read-only info routes ----------

def test_health_shape(client):
    r = client.get("/api/health")
    assert r.status_code == 200
    body = r.json()
    for key in ("ok", "version", "backend", "model", "models", "depts", "agents",
                "routines", "roster", "skills", "tools", "mcp"):
        assert key in body
    assert body["backend"] == "langgraph"


def test_agents_shape(client):
    r = client.get("/api/agents")
    assert r.status_code == 200
    body = r.json()
    assert "agents" in body and isinstance(body["agents"], list)
    assert len(body["agents"]) > 0
    first = body["agents"][0]
    for key in ("id", "department", "lead", "name", "role", "does", "tools"):
        assert key in first


def test_skills_shape(client):
    r = client.get("/api/skills")
    assert r.status_code == 200


def test_lessons_shape(client):
    r = client.get("/api/lessons")
    assert r.status_code == 200
    assert "dir" in r.json() and "agents" in r.json()


def test_mcp_shape(client):
    r = client.get("/api/mcp")
    assert r.status_code == 200
    assert r.json()["tools"] is True


def test_brain_shape(client):
    r = client.get("/api/brain")
    assert r.status_code == 200


def test_usage_shape(client):
    r = client.get("/api/usage")
    assert r.status_code == 200


# ---------- tasks ----------

def test_list_tasks_empty(client):
    r = client.get("/api/tasks")
    assert r.status_code == 200
    assert r.json() == []


def test_create_task_requires_dept_and_text(client):
    r = client.post("/api/tasks", json={"dept": "fin"})
    assert r.status_code == 400
    r = client.post("/api/tasks", json={"dept": "not-a-dept", "text": "do a thing"})
    assert r.status_code == 400


def test_create_task_routes_and_persists(client):
    r = client.post("/api/tasks", json={"dept": "fin", "text": "chase overdue invoices"})
    assert r.status_code == 200
    task = r.json()
    for key in ("id", "dept", "text", "state", "agent", "title", "plan", "eta_minutes", "why", "needsOk"):
        assert key in task
    assert task["dept"] == "fin"
    assert task["state"] == "next"

    listed = client.get("/api/tasks").json()
    assert any(t["id"] == task["id"] for t in listed)


def test_run_blocks_and_returns_completed_task(client):
    created = client.post("/api/tasks", json={"dept": "fin", "text": "chase overdue invoices"}).json()
    r = client.post(f"/api/tasks/{created['id']}/run")
    assert r.status_code == 200
    task = r.json()
    # /run is synchronous: by the time this response lands, the task is already "done".
    assert task["state"] == "done"
    assert task["result"] == "mocked agent output"


def test_revise_blocks_and_returns_completed_task(client):
    created = client.post("/api/tasks", json={"dept": "fin", "text": "chase overdue invoices"}).json()
    client.post(f"/api/tasks/{created['id']}/run")
    r = client.post(f"/api/tasks/{created['id']}/revise", json={"feedback": "shorter please"})
    assert r.status_code == 200
    assert r.json()["state"] == "done"


def test_run_unknown_task_404(client):
    r = client.post("/api/tasks/not-a-real-id/run")
    assert r.status_code == 404


def test_approve_acks_immediately_before_background_work_finishes(client, fake_store, monkeypatch, graph_checkpointer):
    created = client.post("/api/tasks", json={"dept": "fin", "text": "chase overdue invoices"}).json()
    _seed_waiting_task(fake_store[created["id"]])

    finish_event = asyncio.Event()

    async def slow_ask_with_tools(messages, tools, model_key=None, max_tokens=4096):
        await finish_event.wait()
        return {"content": "finally done", "tool_calls": []}

    monkeypatch.setattr(engine, "ask_with_tools", slow_ask_with_tools)

    r = client.post(f"/api/tasks/{created['id']}/approve")
    # The HTTP response must come back before the slow background work completes —
    # that's the whole point of the asyncio.create_task ack-then-continue pattern.
    assert r.status_code == 200
    assert r.json() == {"ok": True, "id": created["id"], "state": "doing"}
    assert fake_store[created["id"]]["state"] == "doing"

    finish_event.set()


def test_approve_requires_waiting_state(client):
    created = client.post("/api/tasks", json={"dept": "fin", "text": "chase overdue invoices"}).json()
    # freshly created task is "next", not "waiting"
    r = client.post(f"/api/tasks/{created['id']}/approve")
    assert r.status_code == 400


def test_reject_acks_immediately(client, fake_store, graph_checkpointer):
    created = client.post("/api/tasks", json={"dept": "fin", "text": "chase overdue invoices"}).json()
    _seed_waiting_task(fake_store[created["id"]])
    r = client.post(f"/api/tasks/{created['id']}/reject", json={"feedback": "no, redo this"})
    assert r.status_code == 200
    assert r.json() == {"ok": True, "id": created["id"], "state": "doing"}


def test_delete_task(client, fake_store):
    created = client.post("/api/tasks", json={"dept": "fin", "text": "chase overdue invoices"}).json()
    r = client.delete(f"/api/tasks/{created['id']}")
    assert r.status_code == 200
    assert r.json() == {"ok": True}
    assert created["id"] not in fake_store


# ---------- routines ----------

def test_list_routines_shape(client):
    r = client.get("/api/routines")
    assert r.status_code == 200
    body = r.json()
    for key in ("routines", "depts", "path", "problems"):
        assert key in body


def test_create_routine_rejects_unknown_dept(client):
    r = client.post("/api/routines", json={"dept": "not-a-dept", "text": "do a thing", "when": {"kind": "daily", "at": "09:00"}})
    assert r.status_code == 400


def test_create_routine_rejects_non_routine_department(client):
    # per CLAUDE.md: routines are Content/Finance/Revenue only this release
    r = client.post("/api/routines", json={"dept": "engineering", "text": "ship the release notes", "when": {"kind": "daily", "at": "09:00"}})
    assert r.status_code == 400


def test_create_routine_requires_text(client):
    r = client.post("/api/routines", json={"dept": "fin", "text": "", "when": {"kind": "daily", "at": "09:00"}})
    assert r.status_code == 400


def test_create_routine_requires_a_resolvable_schedule(client):
    r = client.post("/api/routines", json={"dept": "fin", "text": "chase overdue invoices"})
    assert r.status_code == 400


def test_create_run_pause_resume_patch_delete_routine_roundtrip(client):
    created = client.post("/api/routines", json={
        "dept": "fin", "text": "list overdue invoices every Monday", "when": {"kind": "weekly", "days": [1], "at": "09:00"},
    })
    assert created.status_code == 200
    routine = created.json()["routine"]
    rid = routine["id"]

    listed = client.get("/api/routines").json()
    assert any(r["id"] == rid for r in listed["routines"])

    assert client.post(f"/api/routines/{rid}/run").status_code == 200
    assert client.post(f"/api/routines/{rid}/pause").status_code == 200
    paused = next(r for r in client.get("/api/routines").json()["routines"] if r["id"] == rid)
    assert paused["paused"] is True

    assert client.post(f"/api/routines/{rid}/resume").status_code == 200
    resumed = next(r for r in client.get("/api/routines").json()["routines"] if r["id"] == rid)
    assert resumed["paused"] is False

    assert client.post(f"/api/routines/{rid}", json={"title": "Renamed"}).status_code == 200
    patched = next(r for r in client.get("/api/routines").json()["routines"] if r["id"] == rid)
    assert patched["title"] == "Renamed"

    assert client.delete(f"/api/routines/{rid}").status_code == 200
    assert not any(r["id"] == rid for r in client.get("/api/routines").json()["routines"])


def test_patch_unknown_routine_404(client):
    r = client.post("/api/routines/not-a-real-id", json={"title": "x"})
    assert r.status_code == 404


# ---------- chat ----------

def test_chat_requires_known_agent(client):
    r = client.post("/api/chat", json={"agent": "not-a-real-agent", "text": "hi"})
    assert r.status_code == 400


def test_chat_returns_reply(client):
    agents = client.get("/api/agents").json()["agents"]
    fin_agent = next(a for a in agents if a["department"] == "fin")
    r = client.post("/api/chat", json={"agent": fin_agent["id"], "text": "what's overdue?", "history": []})
    assert r.status_code == 200
    assert "reply" in r.json()


# ---------- fallback ----------

def test_unknown_route_404(client):
    r = client.get("/api/not-a-real-route")
    assert r.status_code == 404
