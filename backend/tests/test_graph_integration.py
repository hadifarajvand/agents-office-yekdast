"""Checkpointer wiring for app/graph/engine (Task 1). Exercises compile_graph()
against an in-memory checkpointer (same BaseCheckpointSaver interface
AsyncPostgresSaver implements) since no host port is mapped to the
docker-compose Postgres container for a real connection from here. Confirms
the graph is actually checkpointed (state survives a second invoke on the
same thread) and that run_task still works through a recompiled graph.
"""
import asyncio
from pathlib import Path

from langgraph.checkpoint.memory import InMemorySaver

from app.graph import engine
from app.roster import defaults


def test_compile_graph_without_checkpointer_runs(monkeypatch):
    async def fake_ask(system, user, model_key=None):
        return "ok"

    monkeypatch.setattr(engine, "ask", fake_ask)
    engine.compile_graph(checkpointer=None)
    out = asyncio.run(engine._compiled.ainvoke(
        {"system": "s", "user": "u", "model_key": "haiku", "result": ""},
        config={"configurable": {"thread_id": "t1"}},
    ))
    assert out["result"] == "ok"


def test_compile_graph_with_checkpointer_persists_state(monkeypatch):
    async def fake_ask(system, user, model_key=None):
        return "first run"

    monkeypatch.setattr(engine, "ask", fake_ask)
    saver = InMemorySaver()
    engine.compile_graph(checkpointer=saver)
    config = {"configurable": {"thread_id": "persist-me"}}

    asyncio.run(engine._compiled.ainvoke(
        {"system": "s", "user": "u", "model_key": "haiku", "result": ""}, config=config,
    ))
    state = engine._compiled.get_state(config)
    assert state.values["result"] == "first run"
    engine.compile_graph(checkpointer=None)


def test_run_task_works_through_recompiled_graph(monkeypatch, tmp_path: Path):
    async def fake_ask(system, user, model_key=None):
        return "drafted"

    monkeypatch.setattr(engine, "ask", fake_ask)
    engine.compile_graph(checkpointer=InMemorySaver())
    agents = defaults()
    agent = next(a for a in agents if a.department == "fin")
    task = {"id": "task-1", "dept": "fin", "title": "chase invoices", "text": "chase overdue invoices"}

    out = asyncio.run(engine.run_task(
        task, None, "draft", agent, agents, skills=type("S", (), {"names": lambda self, a: [], "prompt_text": lambda self, a: ""})(),
        brain_path=tmp_path, office_model=None, office_effort=None,
    ))
    assert out["result"] == "drafted"
    engine.compile_graph(checkpointer=None)
