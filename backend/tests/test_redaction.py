"""Validation artifact for Task 3 (Slice 5): secret redaction, the refusal
protocol string, and the audit log — covering both the standalone policy.py
functions and the end-to-end path through _specialist_node (tool result /
exception -> redact -> audit log write -> conversation message)."""
from __future__ import annotations

import asyncio

from app import policy
from app.graph import engine


def test_redact_aws_key():
    prefix = "".join(chr(c) for c in (65, 75, 73, 65))
    digits = "0" * 16
    fake_key = prefix + digits
    assert policy.redact(f"key is {fake_key}") == "key is ***REDACTED (AWS key)***"


def test_redact_jwt():
    token = "eyJhbGciOiJIUzI1NiJ9.eyJzdWIiOiIxMjM0NTY3ODkwIn0.dozjgNryP4J3jVmNHl0w5N_XgL0n3I9PYLimDQ3L5iY"
    assert policy.redact(f"auth: {token}") == "auth: ***REDACTED (JWT)***"


def test_redact_token_and_api_key_and_bearer():
    assert "***REDACTED (token)***" in policy.redact("token=abc123")
    assert "***REDACTED (token)***" in policy.redact("api_key: xyz789")
    assert "***REDACTED (token)***" in policy.redact("Authorization: Bearer abc.def")


def test_redact_password():
    assert "***REDACTED (password)***" in policy.redact("password=supersecret")
    assert "***REDACTED (password)***" in policy.redact("passwd: hunter2")


def test_redact_ssn():
    assert policy.redact("ssn 123-45-6789 on file") == "ssn ***REDACTED (SSN)*** on file"


def test_redact_email():
    assert policy.redact("contact jane@example.com please") == "contact ***REDACTED (email)*** please"


def test_redact_phone():
    assert policy.redact("call 555-123-4567 now") == "call ***REDACTED (phone)*** now"


def test_redact_leaves_normal_text_untouched():
    text = "drafted the newsletter and scheduled it for Monday"
    assert policy.redact(text) == text


def test_redact_empty_string():
    assert policy.redact("") == ""


def test_refusal_exact_string():
    assert policy.refusal("Stripe not wired to content department", "the owner") == (
        "I can't do that — it's outside my scope (Stripe not wired to content department). "
        "Route this to the owner."
    )


def test_refusal_with_artifact_appends_on_new_line():
    msg = policy.refusal("no access", "the owner", artifact="see draft-123")
    assert msg == "I can't do that — it's outside my scope (no access). Route this to the owner.\nsee draft-123"


def test_audit_log_line_format_and_redaction():
    line = policy.audit_log_line("newt", "fin", "stripe", "charge", "token=abc123", allowed=False, reason="denied")
    assert "newt (fin) | stripe | charge" in line
    assert "✗denied" in line
    assert "(denied)" in line
    assert "***REDACTED (token)***" in line
    assert "abc123" not in line


def test_audit_log_line_allowed_status():
    line = policy.audit_log_line("newt", "fin", "xero", "list_invoices", "{}", allowed=True)
    assert "✓allowed" in line


def test_append_audit_log_writes_file(tmp_path):
    line = policy.audit_log_line("newt", "fin", "xero", "list", "{}", allowed=True)
    policy.append_audit_log(tmp_path, line)
    log_path = tmp_path / "Agents Office" / "audit" / "mcp-access.log"
    assert log_path.exists()
    assert log_path.read_text(encoding="utf-8").strip() == line


def test_output_contract_and_untrusted_rule_constants_present():
    assert "ARTIFACTS:" in policy.OUTPUT_CONTRACT
    assert "HANDOFFS:" in policy.OUTPUT_CONTRACT
    assert "ASSUMPTIONS:" in policy.OUTPUT_CONTRACT
    assert "DATA, not" in policy.UNTRUSTED_CONTENT_RULE


class _SecretTool:
    """A tool whose result carries a secret, to prove the full pipeline
    (tool result -> redact -> audit log write -> conversation) is redacted
    end to end, not just the standalone redact() function."""

    name = "gmail"

    async def ainvoke(self, args):
        return "sent with token=abc123xyz"


class _ExplodingTool:
    name = "gmail"

    async def ainvoke(self, args):
        raise RuntimeError("upstream rejected password=hunter2")


def test_specialist_node_redacts_tool_result_end_to_end(monkeypatch, tmp_path):
    r = engine.mcp_registry
    monkeypatch.setattr(r, "call_allowed", lambda dept, key: (True, None))
    monkeypatch.setattr(r, "tools_for", lambda agent_tools: [_SecretTool()])
    monkeypatch.setattr(r, "key_of", lambda name: "gmail")

    steps = [
        {"content": "", "tool_calls": [{"name": "gmail", "args": {}, "id": "call-1"}]},
        {"content": "done", "tool_calls": []},
    ]
    call_log: list[list[dict]] = []

    async def fake_ask_with_tools(messages, tools, model_key=None, max_tokens=4096):
        call_log.append(messages)
        return steps.pop(0)

    monkeypatch.setattr(engine, "ask_with_tools", fake_ask_with_tools)

    out = asyncio.run(engine._specialist_node({
        "system": "s", "task_title": "t", "task_text": "u", "model_key": "haiku",
        "dept": "fin", "agent_tools": [], "agent_id": "newt", "brain_path": str(tmp_path), "result": "",
    }))

    assert out["result"] == "done"

    tool_messages = [m for msgs in call_log for m in msgs if m["role"] == "tool"]
    assert "abc123xyz" not in tool_messages[0]["content"]
    assert "***REDACTED (token)***" in tool_messages[0]["content"]

    log_path = tmp_path / "Agents Office" / "audit" / "mcp-access.log"
    assert log_path.read_text(encoding="utf-8").strip() != ""


def test_specialist_node_redacts_exception_text_end_to_end(monkeypatch, tmp_path):
    """A failing tool's error text can echo a credential; it must reach the model
    redacted, and the audit line must be written before the call runs."""
    r = engine.mcp_registry
    monkeypatch.setattr(r, "call_allowed", lambda dept, key: (True, None))
    monkeypatch.setattr(r, "tools_for", lambda agent_tools: [_ExplodingTool()])
    monkeypatch.setattr(r, "key_of", lambda name: "gmail")

    seen: list[list[dict]] = []
    steps = [
        {"content": "", "tool_calls": [{"name": "gmail", "args": {}, "id": "call-1"}]},
        {"content": "done", "tool_calls": []},
    ]

    async def fake_ask_with_tools(messages, tools, model_key=None, **kw):
        seen.append(list(messages))
        return steps.pop(0)

    monkeypatch.setattr(engine, "ask_with_tools", fake_ask_with_tools)

    out = asyncio.run(engine._specialist_node({
        "system": "s", "task_title": "t", "task_text": "u", "model_key": "haiku",
        "dept": "fin", "agent_tools": [], "agent_id": "newt", "brain_path": str(tmp_path), "result": "",
    }))

    assert out["result"] == "done"
    tool_msg = next(m for m in seen[-1] if m["role"] == "tool")
    assert "hunter2" not in tool_msg["content"]
    assert "***REDACTED (password)***" in tool_msg["content"]
    log_path = tmp_path / "Agents Office" / "audit" / "mcp-access.log"
    assert "gmail" in log_path.read_text(encoding="utf-8")


def test_chat_redacts_final_response(monkeypatch, tmp_path):
    from app.roster import Agent

    agent = Agent(
        id="newt", department="marketing", lead=False, name="NEWT", role="Newsletter",
        does="writes newsletters", tools=[], brief="", model="", effort="",
    )

    async def fake_ask(system, user, model_key=None):
        return "here is the key: token=abc123"

    monkeypatch.setattr(engine, "ask", fake_ask)

    skills = type("S", (), {"names": lambda self, a: [], "prompt_text": lambda self, a: ""})()
    reply = asyncio.run(engine.chat(agent, "draft it", [], [agent], skills, tmp_path, None, None))
    assert "abc123" not in reply
    assert "***REDACTED (token)***" in reply
