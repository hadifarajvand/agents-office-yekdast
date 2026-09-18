"""LangGraph State definitions for Agent Office

Core state schema for multi-agent orchestration.
"""

from typing import Any, Literal, Optional

from typing_extensions import TypedDict


class Message(TypedDict):
    """Agent message in task execution"""

    agent_id: str
    role: Literal["user", "assistant"]
    content: str
    timestamp: float
    tools_used: list[str]


class SpecialistResult(TypedDict):
    """Result from a specialist agent"""

    specialist_id: str
    success: bool
    result: str
    error: Optional[str]
    tokens_used: int
    timestamp: float


class OfficeState(TypedDict):
    """Main state for task execution through Agent Office

    Flows through LangGraph nodes, checkpointed at critical points.
    """

    # Task Identity
    task_id: str
    created_by: str
    created_at: float

    # Task Content
    task_text: str
    department: str
    model: str
    effort: str

    # Execution State
    status: Literal[
        "pending",
        "routed",
        "planning",
        "in_progress",
        "synthesis",
        "pending_approval",
        "completed",
        "failed",
        "escalated",
    ]
    assigned_lead: Optional[str]
    assigned_agents: list[str]

    # Knowledge & Context
    brain_context: list[dict]
    brain_context_query: Optional[str]

    # Execution Results
    messages: list[Message]
    working_memory: dict[str, Any]
    specialist_results: dict[str, SpecialistResult]
    deliverable: Optional[str]

    # Error Tracking
    errors: list[str]
    retry_count: int
    last_error: Optional[str]

    # Resource Tracking
    used_tools: list[str]
    total_tokens: int
    cost_usd: float
    start_time: float
    last_checkpoint: float

    # Approval & Feedback
    approval_status: Literal["pending", "approved", "rejected", "approved_auto"]
    approval_feedback: Optional[str]
    user_feedback: Optional[str]

    # Metadata
    version: int
    checkpoint_node: Optional[str]


class AgentConfig(TypedDict):
    """Configuration for an agent"""

    agent_id: str
    agent_name: str
    department: str
    is_lead: bool
    model: str
    system_prompt: str
    tools: list[str]
    max_tokens: int
    temperature: float
    tools_budget: dict[str, int]


class DepartmentConfig(TypedDict):
    """Configuration for a department"""

    department_id: str
    name: str
    lead_agent_id: str
    specialist_agents: list[str]
    mcp_tools: list[str]
    approval_required: bool
