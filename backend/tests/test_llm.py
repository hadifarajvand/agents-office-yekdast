"""The model layer: router client construction, metering, model-swap detection, budget cap."""
from __future__ import annotations

import asyncio

import pytest
from langchain_core.messages import AIMessage

from app import llm


class FakeChatModel:
    def __init__(self, reply: str, model_seen: str, tokens=(100, 20)):
        self.reply, self.model_seen, self.tokens = reply, model_seen, tokens

    async def ainvoke(self, messages):
        return AIMessage(content=self.reply, response_metadata={"model_name": self.model_seen},
                         usage_metadata={"input_tokens": self.tokens[0], "output_tokens": self.tokens[1],
                                         "total_tokens": sum(self.tokens)})


def use(monkeypatch, model: FakeChatModel):
    monkeypatch.setattr(llm, "_client", lambda mid, max_tokens: model)


def test_same_model_ignores_router_prefix_but_catches_swaps():
    assert llm.same_model("cc/claude-haiku-4-5-20251001", "claude-haiku-4-5-20251001")
    assert llm.same_model("kr/glm-5", "glm-5")
    assert llm.same_model("cc/claude-opus-5[1m]", "claude-opus-5")
    assert not llm.same_model("cc/claude-haiku-4-5-20251001", "glm-4.5-air")
    assert llm.same_model("kr/glm-5", "")  # router did not say: cannot prove a swap


def test_meter_records_tokens_and_flags_a_silent_fallback(monkeypatch):
    use(monkeypatch, FakeChatModel("hi", "some-free-model"))
    meter = llm.RunMeter(label="t")
    tok = llm.current_meter.set(meter)
    try:
        assert asyncio.run(llm.ask("s", "u", model="cc/claude-haiku-4-5-20251001")) == "hi"
    finally:
        llm.current_meter.reset(tok)
    assert meter.tokens == 120
    assert meter.valid is False and "some-free-model" in meter.mismatches[0]


def test_budget_cap_stops_the_run(monkeypatch):
    use(monkeypatch, FakeChatModel("hi", "glm-5", tokens=(1000, 1000)))
    monkeypatch.setattr(llm, "_price", lambda model, tokens: 0.6)
    meter = llm.RunMeter(label="job", usd_cap=1.0)
    tok = llm.current_meter.set(meter)
    try:
        asyncio.run(llm.ask("s", "u", role="research"))
        with pytest.raises(llm.BudgetExceeded):
            asyncio.run(llm.ask("s", "u", role="research"))
    finally:
        llm.current_meter.reset(tok)


def test_roles_resolve_to_pinned_router_ids():
    assert llm.role_model("builder").endswith("claude-haiku-4-5-20251001")
    assert llm.role_model("research") == "kr/glm-5"
    assert llm.resolve_model(model="x/y") == "x/y"


def test_openai_client_points_at_router_v1_once(monkeypatch):
    monkeypatch.setenv("ROUTER_BASE_URL", "http://localhost:20128/v1")
    monkeypatch.delenv("ROUTER_FORMAT", raising=False)
    c = llm._client("kr/glm-5", 256)
    assert str(c.openai_api_base).rstrip("/") == "http://localhost:20128/v1"
    assert c.model_name == "kr/glm-5"


def test_anthropic_client_uses_bare_base_url(monkeypatch):
    monkeypatch.setenv("ROUTER_BASE_URL", "http://localhost:20128")
    monkeypatch.setenv("ROUTER_FORMAT", "anthropic")
    c = llm._client("cc/claude-haiku-4-5-20251001", 256)
    assert c.anthropic_api_url.rstrip("/") == "http://localhost:20128"
    assert c.model == "cc/claude-haiku-4-5-20251001"


def test_parse_json_tolerates_fences():
    assert llm.parse_json('```json\n{"a": 1}\n```') == {"a": 1}
