"""Tests for ModelRouter — tier resolution, fallback, and budget control."""

from __future__ import annotations

import pytest
from unittest.mock import AsyncMock, patch, MagicMock
from pathlib import Path


@pytest.fixture
def routing_yaml(tmp_path: Path) -> Path:
    """Create a minimal routing.yaml for tests."""
    config = tmp_path / "routing.yaml"
    config.write_text("""
tiers:
  reasoning_fast:
    description: Test tier
    primary: claude-sonnet-4-20250514
    fallbacks:
      - claude-haiku-4-5-20251001
    max_tokens: 4096
    temperature: 0.2

  local_only:
    description: Local fallback
    primary: ollama/llama3.1
    fallbacks: []
    max_tokens: 2048
    temperature: 0.3

cost_controls:
  daily_budget_usd: 1.0
  warn_at_pct: 80
""")
    return config


@pytest.fixture
def catalog_yaml(tmp_path: Path) -> Path:
    """Create a minimal catalog.yaml for tests."""
    config = tmp_path / "catalog.yaml"
    config.write_text("""
models:
  claude-sonnet-4-20250514:
    provider: anthropic
    litellm_id: anthropic/claude-sonnet-4-20250514
    cost_per_1k_input: 0.003
    cost_per_1k_output: 0.015
    context_window: 200000

  claude-haiku-4-5-20251001:
    provider: anthropic
    litellm_id: anthropic/claude-haiku-4-5-20251001
    cost_per_1k_input: 0.0008
    cost_per_1k_output: 0.004
    context_window: 200000

  ollama/llama3.1:
    provider: ollama
    litellm_id: ollama/llama3.1
    cost_per_1k_input: 0.0
    cost_per_1k_output: 0.0
    context_window: 128000
""")
    return config


class TestTierResolution:
    """Test that tiers resolve to the correct model from routing.yaml."""

    def test_select_returns_primary_and_fallbacks(self, routing_yaml, catalog_yaml):
        from backbone.runtime.model_client import ModelRouter

        router = ModelRouter(routing_path=routing_yaml, catalog_path=catalog_yaml)
        result = router.select("reasoning_fast")

        assert result.primary == "anthropic/claude-sonnet-4-20250514"
        assert result.fallbacks == ["anthropic/claude-haiku-4-5-20251001"]
        assert result.max_tokens == 4096
        assert result.temperature == 0.2

    def test_select_unknown_tier_raises(self, routing_yaml, catalog_yaml):
        from backbone.runtime.model_client import ModelRouter

        router = ModelRouter(routing_path=routing_yaml, catalog_path=catalog_yaml)

        with pytest.raises(KeyError):
            router.select("nonexistent_tier")


class TestFallbackBehavior:
    """Test that fallback order is honored when primary fails."""

    @pytest.mark.asyncio
    async def test_fallback_on_primary_failure(self, routing_yaml, catalog_yaml):
        from backbone.runtime.model_client import ModelRouter

        router = ModelRouter(routing_path=routing_yaml, catalog_path=catalog_yaml)

        call_count = {"n": 0}

        async def mock_litellm_call(**kwargs):
            call_count["n"] += 1
            if "sonnet" in kwargs.get("model", ""):
                raise Exception("Primary unavailable")
            # Haiku fallback succeeds
            mock_response = MagicMock()
            mock_response.choices = [MagicMock()]
            mock_response.choices[0].message.content = "Fallback response"
            mock_response.usage = MagicMock()
            mock_response.usage.prompt_tokens = 10
            mock_response.usage.completion_tokens = 20
            return mock_response

        with patch("backbone.runtime.model_client.acompletion", side_effect=mock_litellm_call):
            result = await router.complete(
                tier="reasoning_fast",
                messages=[{"role": "user", "content": "Hello"}],
            )

        assert result.content == "Fallback response"
        assert result.status == "ok"
        assert call_count["n"] == 2  # primary failed, fallback succeeded


class TestBudgetControl:
    """Test that budget exceeded routes to local_only."""

    @pytest.mark.asyncio
    async def test_budget_exceeded_routes_to_local(self, routing_yaml, catalog_yaml):
        from backbone.runtime.model_client import ModelRouter

        router = ModelRouter(routing_path=routing_yaml, catalog_path=catalog_yaml)
        # Simulate budget exceeded
        router._daily_spend_usd = 2.0  # Over the 1.0 budget

        async def mock_litellm_call(**kwargs):
            mock_response = MagicMock()
            mock_response.choices = [MagicMock()]
            mock_response.choices[0].message.content = "Local response"
            mock_response.usage = MagicMock()
            mock_response.usage.prompt_tokens = 10
            mock_response.usage.completion_tokens = 20
            return mock_response

        with patch("backbone.runtime.model_client.acompletion", side_effect=mock_litellm_call):
            result = await router.complete(
                tier="reasoning_fast",
                messages=[{"role": "user", "content": "Hello"}],
            )

        assert result.status == "ok"
        # Should have been routed to local_only tier's primary
        assert result.model_used == "ollama/llama3.1"

    @pytest.mark.asyncio
    async def test_all_fallbacks_fail_returns_unavailable(self, routing_yaml, catalog_yaml):
        from backbone.runtime.model_client import ModelRouter

        router = ModelRouter(routing_path=routing_yaml, catalog_path=catalog_yaml)

        async def mock_litellm_call(**kwargs):
            raise Exception("All models down")

        with patch("backbone.runtime.model_client.acompletion", side_effect=mock_litellm_call):
            result = await router.complete(
                tier="reasoning_fast",
                messages=[{"role": "user", "content": "Hello"}],
            )

        assert result.status == "model_unavailable"
