"""Agent API routes — browse endpoint and agent dispatch."""

from __future__ import annotations

from pydantic import BaseModel, Field
from fastapi import APIRouter, HTTPException

import structlog

logger = structlog.get_logger("routes.agents")

router = APIRouter(prefix="/agent", tags=["agents"])


class BrowseRequest(BaseModel):
    """Request body for the /agent/browse endpoint."""

    tab_url: str = Field(..., description="URL of the active browser tab")
    tab_content: str = Field(..., max_length=20000, description="Text content of the tab")
    user_query: str = Field(..., max_length=2000, description="User question about the page")


class BrowseResponse(BaseModel):
    """Response from the browse agent."""

    status: str
    answer: str = ""
    model_used: str = ""
    url: str = ""


@router.post("/browse", response_model=BrowseResponse)
async def browse_agent(request: BrowseRequest) -> BrowseResponse:
    """Process a browse request from the Chrome extension.

    Captures active tab context and runs it through a browsing-oriented agent
    via the ModelRouter. Tab content is sanitized before processing.

    This endpoint mirrors the Claude-in-Chrome pattern and is gated behind
    an explicit user action per tab (no background surveillance).
    """
    try:
        from backbone.runtime.browse_handler import handle_browse_request
        from backbone.runtime.model_client import ModelRouter

        router_instance = ModelRouter()

        result = await handle_browse_request(
            tab_url=request.tab_url,
            tab_content=request.tab_content,
            user_query=request.user_query,
            router=router_instance,
        )

        return BrowseResponse(
            status=result.get("status", "error"),
            answer=result.get("answer", ""),
            model_used=result.get("model_used", ""),
            url=result.get("url", request.tab_url),
        )

    except Exception as exc:
        logger.error("browse_agent_error", error=str(exc))
        raise HTTPException(status_code=500, detail="Agent processing failed") from exc


class AgentRunRequest(BaseModel):
    """Request body for running a specific agent."""

    agent_id: str = Field(..., description="Agent ID from the registry")
    prompt: str = Field(..., max_length=10000, description="Prompt to send to the agent")
    context: str | None = Field(None, max_length=20000, description="Optional context")


class AgentRunResponse(BaseModel):
    """Response from an agent run."""

    status: str
    agent_id: str
    output: str = ""
    model_used: str = ""
    tier: str = ""


@router.post("/run", response_model=AgentRunResponse)
async def run_agent(request: AgentRunRequest) -> AgentRunResponse:
    """Run a specific agent from the registry by ID.

    Resolves the agent definition, applies its tier and system prompt,
    and routes through the ModelRouter with guardrails.
    """
    try:
        from backbone.runtime.agent_sdk import AgentSDK

        sdk = AgentSDK()
        result = await sdk.run_agent(
            agent_id=request.agent_id,
            prompt=request.prompt,
            context=request.context,
        )

        return AgentRunResponse(
            status=result.get("status", "error"),
            agent_id=request.agent_id,
            output=result.get("output", ""),
            model_used=result.get("model_used", ""),
            tier=result.get("tier", ""),
        )

    except KeyError as exc:
        raise HTTPException(status_code=404, detail=f"Agent not found: {request.agent_id}") from exc
    except Exception as exc:
        logger.error("agent_run_error", agent_id=request.agent_id, error=str(exc))
        raise HTTPException(status_code=500, detail="Agent execution failed") from exc
