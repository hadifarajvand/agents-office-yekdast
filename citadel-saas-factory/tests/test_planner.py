"""Tests for the planner-executor-critic orchestration loop."""

from __future__ import annotations

import pytest
from unittest.mock import AsyncMock, MagicMock


class TestPlannerLoop:
    """Test the plan -> execute -> critique loop with stop-gate."""

    @pytest.mark.asyncio
    async def test_critic_can_reject_and_replan(self):
        from backbone.orchestrator.planner import PlannerLoop

        call_log = []

        async def mock_complete(tier, messages, **kwargs):
            prompt = messages[-1]["content"]
            call_log.append(prompt[:30])

            if "Create a plan" in prompt:
                return MagicMock(
                    content='{"steps": [{"id": "s1", "action": "search", "input": "test"}]}',
                    status="ok",
                )
            if "Execute step" in prompt:
                return MagicMock(content="Step result: found 3 items", status="ok")
            if "Critique" in prompt:
                if len([c for c in call_log if "Critique" in c]) <= 1:
                    return MagicMock(
                        content='{"approved": false, "reason": "Missing detail", "revised_plan": {"steps": [{"id": "s1", "action": "search", "input": "test detailed"}]}}',
                        status="ok",
                    )
                return MagicMock(content='{"approved": true, "reason": "Looks good"}', status="ok")
            return MagicMock(content="done", status="ok")

        mock_router = AsyncMock()
        mock_router.complete = AsyncMock(side_effect=mock_complete)

        planner = PlannerLoop(router=mock_router, max_replans=3)
        result = await planner.run(goal="Find all API endpoints in the codebase")

        assert result.status == "ok"
        assert result.iterations >= 2  # At least one reject + one approve

    @pytest.mark.asyncio
    async def test_max_depth_prevents_infinite_loop(self):
        from backbone.orchestrator.planner import PlannerLoop

        async def always_reject(tier, messages, **kwargs):
            prompt = messages[-1]["content"]
            if "Create a plan" in prompt or "revised_plan" in prompt:
                return MagicMock(
                    content='{"steps": [{"id": "s1", "action": "noop", "input": "x"}]}',
                    status="ok",
                )
            if "Execute" in prompt:
                return MagicMock(content="executed", status="ok")
            if "Critique" in prompt:
                return MagicMock(
                    content='{"approved": false, "reason": "Not good enough", "revised_plan": {"steps": [{"id": "s1", "action": "noop", "input": "x"}]}}',
                    status="ok",
                )
            return MagicMock(content="done", status="ok")

        mock_router = AsyncMock()
        mock_router.complete = AsyncMock(side_effect=always_reject)

        planner = PlannerLoop(router=mock_router, max_replans=2)
        result = await planner.run(goal="Impossible task")

        assert result.status in ("ok", "max_replans_reached")
        assert result.iterations <= 3  # 1 initial + 2 replans max
