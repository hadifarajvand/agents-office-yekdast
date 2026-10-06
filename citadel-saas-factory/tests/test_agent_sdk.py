"""Tests for the Agent SDK — resolution, execution, and sub-agent spawning."""

from __future__ import annotations

import pytest
from unittest.mock import AsyncMock, MagicMock, patch


class TestAgentSDK:
    """Test agent resolution and execution."""

    def test_resolve_agent_from_registry(self):
        from backbone.runtime.agent_sdk import AgentSDK

        sdk = AgentSDK()
        agent = sdk.resolve_agent("eng-api-designer")

        assert agent["id"] == "eng-api-designer"
        assert agent["domain"] == "engineering"
        assert agent["tier"] == "reasoning_fast"
        assert agent["system_prompt"] != ""
        assert agent["rag_enabled"] is True

    def test_resolve_unknown_agent_raises(self):
        from backbone.runtime.agent_sdk import AgentSDK

        sdk = AgentSDK()
        with pytest.raises(KeyError):
            sdk.resolve_agent("nonexistent-agent-xyz")

    @pytest.mark.asyncio
    async def test_run_agent_calls_router_with_system_prompt(self):
        from backbone.runtime.agent_sdk import AgentSDK

        mock_router = AsyncMock()
        mock_router.complete.return_value = MagicMock(
            content="API endpoint designed successfully.",
            status="ok",
            model_used="anthropic/claude-sonnet-4-20250514",
        )

        sdk = AgentSDK(router=mock_router)
        result = await sdk.run_agent(
            agent_id="eng-api-designer",
            prompt="Design a REST endpoint for user profiles",
        )

        assert result["status"] == "ok"
        assert result["output"] == "API endpoint designed successfully."
        assert result["tier"] == "reasoning_fast"

        # Verify system prompt was included
        call_args = mock_router.complete.call_args
        messages = call_args.kwargs.get("messages") or call_args[1].get("messages")
        assert messages[0]["role"] == "system"
        assert "API Designer" in messages[0]["content"]

    @pytest.mark.asyncio
    async def test_max_spawn_depth_prevents_infinite_recursion(self):
        from backbone.runtime.agent_sdk import AgentSDK, MAX_SPAWN_DEPTH

        mock_router = AsyncMock()
        sdk = AgentSDK(router=mock_router)

        result = await sdk.run_agent(
            agent_id="eng-api-designer",
            prompt="test",
            depth=MAX_SPAWN_DEPTH + 1,
        )

        assert result["status"] == "depth_exceeded"
        mock_router.complete.assert_not_called()

    def test_list_agents_returns_all(self):
        from backbone.runtime.agent_sdk import AgentSDK

        sdk = AgentSDK()
        agents = sdk.list_agents()
        assert len(agents) == 265

    def test_list_agents_filtered_by_domain(self):
        from backbone.runtime.agent_sdk import AgentSDK

        sdk = AgentSDK()
        engineering_agents = sdk.list_agents(domain="engineering")
        assert len(engineering_agents) == 25
        assert all(a["domain"] == "engineering" for a in engineering_agents)
