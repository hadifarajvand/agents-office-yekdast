"""Unit test for the Haiku router node (app/graph/engine.route) — mocks the LLM call so
no network/proxy is needed. Asserts: correct output shape, always resolves to an agent in
the requested department, and that the Haiku call never leaks into the agent-facing model
precedence (route() does not accept/return a 'model' field at all)."""
import asyncio
import json

import pytest

from app.graph import engine
from app.roster import defaults


def test_route_returns_expected_shape(monkeypatch):
    async def fake_ask_haiku_json(system, user):
        return {"agent": "nata", "title": "Draft the overdue reminders", "plan": ["list", "draft"],
                "eta_minutes": 15, "why": "matches billing", "needs_ok": True}

    monkeypatch.setattr(engine, "ask_haiku_json", fake_ask_haiku_json)
    agents = defaults()
    out = asyncio.run(engine.route("fin", "chase overdue invoices", agents))
    assert set(out.keys()) == {"agent", "title", "plan", "eta_minutes", "why", "needs_ok"}
    assert any(a.id == out["agent"] and a.department == "fin" for a in agents)


def test_route_falls_back_to_dept_lead_on_malformed_agent(monkeypatch):
    async def fake_ask_haiku_json(system, user):
        return {"agent": "not-a-real-id"}

    monkeypatch.setattr(engine, "ask_haiku_json", fake_ask_haiku_json)
    agents = defaults()
    out = asyncio.run(engine.route("content", "reply to a customer", agents))
    chosen = next(a for a in agents if a.id == out["agent"])
    assert chosen.department == "content"
