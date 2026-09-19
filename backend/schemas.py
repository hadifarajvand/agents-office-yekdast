"""Type-safe API response schemas using Pydantic

All API responses use these models for validation and documentation.
Ensures frontend always gets properly typed data.
"""

from pydantic import BaseModel, Field
from typing import Optional
from enum import Enum


class TaskStatus(str, Enum):
    """Backend task status values"""

    PENDING = "pending"
    PENDING_APPROVAL = "pending_approval"
    DOING = "doing"
    DONE = "done"


class TaskFrontendState(str, Enum):
    """Frontend state values (mapped from backend status)"""

    NEXT = "next"
    WAITING = "waiting"
    DOING = "doing"
    DONE = "done"
    SCHEDULED = "scheduled"


class TaskResponse(BaseModel):
    """Individual task response schema"""

    id: str = Field(..., description="Task ID")
    agent: str = Field(..., description="Assigned agent ID (never null)")
    dept: str = Field(..., description="Department key")
    title: str = Field(..., description="Task title")
    state: TaskFrontendState = Field(..., description="Frontend state")
    by: str = Field(default="backend", description="Created by")
    createdAt: int = Field(..., description="Created timestamp (ms since epoch)")
    updatedAt: int = Field(..., description="Updated timestamp (ms since epoch)")
    model: str = Field(default="sonnet", description="Model used")
    effort: str = Field(default="low", description="Effort level")
    live: bool = Field(default=True, description="Is live/server task")

    class Config:
        json_schema_extra = {
            "example": {
                "id": "33394502",
                "agent": "elead",
                "dept": "emails",
                "title": "Review overnight inbox",
                "state": "next",
                "by": "api",
                "createdAt": 1789834862654,
                "updatedAt": 1789834862654,
                "model": "sonnet",
                "effort": "low",
                "live": True,
            }
        }


class HealthResponse(BaseModel):
    """Health check response"""

    ok: bool
    status: str
    version: str
    backend: str
    model: str
    brain: str
    agents: int
    notes: int
    timestamp: str


class CreateTaskRequest(BaseModel):
    """Request to create a new task"""

    department: str = Field(..., description="Department key")
    text: str = Field(..., description="Task description")
    model: Optional[str] = Field(None, description="Model override")
    effort: Optional[str] = Field(None, description="Effort override")
    created_by: Optional[str] = Field("api", description="Who created it")


class CreateTaskResponse(BaseModel):
    """Response after creating a task"""

    task_id: str
    status: str
    department: str
    created_at: float
    agent: Optional[str] = None


class EventMessage(BaseModel):
    """SSE event message structure"""

    type: str = Field(..., description="Event type (e.g., task:created)")
    data: dict = Field(..., description="Event payload")
    timestamp: str = Field(..., description="ISO timestamp")


class TaskEventData(BaseModel):
    """Data payload for task events"""

    id: str
    agent: str
    dept: str
    title: str
    status: str
    created_at: Optional[float] = None


class RoutineResponse(BaseModel):
    """Routine/scheduled task response"""

    id: str
    dept: str
    agent: str
    title: str
    desc: str
    when: dict
    paused: bool
    nextAt: int
    model: Optional[str] = None
    effort: Optional[str] = None
