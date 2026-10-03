"""Call-time policy gate validation (Task 2). Unlike test_mcp_policy.py (which checks
MCPRegistry's static allow/deny/department logic in isolation), this file proves the
gate is actually enforced *inside* the specialist's tool-calling loop (app/graph/engine.py),
fresh on every tool-call event — never cached once per task/session. The key scenario the
plan requires: a multi-step run where step 1 calls an allowed tool and succeeds, then a
later step attempts a disallowed tool and is blocked with the exact refusal message, proving
re-evaluation per call rather than a single up-front check.
"""
from __future__ import annotations

import asyncio

from app.graph import engine
from app.mcp import MCPRegistry


class FakeTool:
    def __init__(self, name: str):
        self.name = name
        self.calls: list[dict] = []

    async def ainvoke(self, args):
        self.calls.append(args)
        return f"{self.name} result"


def make_registry():
    r = MCPRegistry()
    r.configure({"mcp": {"allow": [], "deny": [], "departments": {"gmail": ["content"], "stripe": ["fin"]}},
                 "tools": {"web": True}})
    r.servers = [r._make("Gmail", "", "connected"), r._make("Stripe", "", "connected")]
    return r


def test_call_allowed_denies_server_not_wired_to_department():
    r = make_registry()
    allowed, refusal = r.call_allowed("fin", "gmail")
    assert allowed is False
    assert refusal == "I can't do that — it's outside my scope (Gmail not wired to fin department). Route this to the owner."


def test_call_allowed_permits_server_wired_to_department():
    r = make_registry()
    allowed, refusal = r.call_allowed("content", "gmail")
    assert allowed is True
    assert refusal is None


def test_call_allowed_denies_server_outside_allow_deny_policy():
    r = MCPRegistry()
    r.configure({"mcp": {"allow": [], "deny": ["stripe"], "departments": {}}, "tools": {"web": True}})
    r.servers = [r._make("Stripe", "", "connected")]
    allowed, refusal = r.call_allowed("fin", "stripe")
    assert allowed is False
    assert refusal == "I can't do that — it's outside my scope (stripe not wired to fin department). Route this to the owner."


def test_specialist_loop_rechecks_every_call_allow_then_deny(monkeypatch, tmp_path):
    """Step 1 calls an allowed tool (gmail, content dept) and succeeds. Step 2 attempts
    a disallowed tool (stripe, content dept isn't wired to it) and is blocked — proving
    the gate is re-run per call, not decided once for the whole task. Also proves both
    the allowed and denied calls are written to the audit log (Task 3)."""
    r = make_registry()
    monkeypatch.setattr(engine, "mcp_registry", r)

    gmail_tool = FakeTool("gmail")
    stripe_tool = FakeTool("stripe")
    monkeypatch.setattr(r, "tools_for", lambda agent_tools: [gmail_tool, stripe_tool])

    steps = [
        {"content": "", "tool_calls": [{"name": "gmail", "args": {"x": 1}, "id": "call-1"}]},
        {"content": "", "tool_calls": [{"name": "stripe", "args": {"x": 2}, "id": "call-2"}]},
        {"content": "done", "tool_calls": []},
    ]
    call_log: list[list[dict]] = []

    async def fake_ask_with_tools(messages, tools, model_key=None, max_tokens=4096):
        call_log.append(messages)
        return steps.pop(0)

    monkeypatch.setattr(engine, "ask_with_tools", fake_ask_with_tools)

    out = asyncio.run(engine._specialist_node({
        "system": "s", "task_title": "t", "task_text": "u", "model_key": "haiku",
        "dept": "content", "agent_tools": [], "agent_id": "newt", "brain_path": str(tmp_path), "result": "",
    }))

    assert out["result"] == "done"
    assert gmail_tool.calls == [{"x": 1}]
    assert stripe_tool.calls == []

    tool_messages = [m for msgs in call_log for m in msgs if m["role"] == "tool"]
    assert tool_messages[0]["content"] == "gmail result"
    assert tool_messages[1]["content"] == (
        "I can't do that — it's outside my scope (Stripe not wired to content department). Route this to the owner."
    )

    log_path = tmp_path / "Agents Office" / "audit" / "mcp-access.log"
    lines = log_path.read_text(encoding="utf-8").strip().splitlines()
    assert len(lines) == 2
    assert "newt (content) | gmail | gmail" in lines[0] and "✓allowed" in lines[0]
    assert "newt (content) | stripe | stripe" in lines[1] and "✗denied" in lines[1]


def test_specialist_loop_denies_call_matching_boundaries_cannot(monkeypatch, tmp_path):
    """Task 6: a boundaries.cannot line blocks a call even though MCP policy
    would allow it (gmail is wired to content dept here) — the agent's own
    CANNOT contract is checked first and produces the same refusal shape as
    an MCP denial, including the audit log entry and escalation routing."""
    r = make_registry()
    monkeypatch.setattr(engine, "mcp_registry", r)

    gmail_tool = FakeTool("gmail")
    monkeypatch.setattr(r, "tools_for", lambda agent_tools: [gmail_tool])

    steps = [
        {"content": "", "tool_calls": [{"name": "gmail", "args": {"x": 1}, "id": "call-1"}]},
        {"content": "done", "tool_calls": []},
    ]

    async def fake_ask_with_tools(messages, tools, model_key=None, max_tokens=4096):
        return steps.pop(0)

    monkeypatch.setattr(engine, "ask_with_tools", fake_ask_with_tools)

    out = asyncio.run(engine._specialist_node({
        "system": "s", "task_title": "t", "task_text": "u", "model_key": "haiku",
        "dept": "content", "agent_tools": [], "agent_id": "newt",
        "agent_boundaries": {
            "cannot": ["Send gmail messages without review"],
            "escalation": [{"condition": "a blocked send", "target_agent": "cmail"}],
        },
        "brain_path": str(tmp_path), "result": "",
    }))

    assert out["result"] == "done"
    assert gmail_tool.calls == []

    log_path = tmp_path / "Agents Office" / "audit" / "mcp-access.log"
    lines = log_path.read_text(encoding="utf-8").strip().splitlines()
    assert len(lines) == 1
    assert "newt (content) | gmail | gmail" in lines[0] and "✗denied" in lines[0]
    assert "cmail" in lines[0]


def test_specialist_loop_stops_after_max_tool_steps(monkeypatch, tmp_path):
    r = make_registry()
    monkeypatch.setattr(engine, "mcp_registry", r)

    gmail_tool = FakeTool("gmail")
    monkeypatch.setattr(r, "tools_for", lambda agent_tools: [gmail_tool])

    async def always_calls_tool(messages, tools, model_key=None, max_tokens=4096):
        return {"content": "still working", "tool_calls": [{"name": "gmail", "args": {}, "id": "x"}]}

    monkeypatch.setattr(engine, "ask_with_tools", always_calls_tool)

    out = asyncio.run(engine._specialist_node({
        "system": "s", "task_title": "t", "task_text": "u", "model_key": "haiku",
        "dept": "content", "agent_tools": [], "agent_id": "newt", "brain_path": str(tmp_path), "result": "",
    }))

    assert out["result"] == "still working"
    assert len(gmail_tool.calls) == engine.MAX_TOOL_STEPS
