"""Task execution service using LangGraph

Orchestrates task execution through the graph.
"""

import time
import uuid
from typing import Optional

from backend.langgraph.graphs import office_graph
from backend.langgraph.state import OfficeState
from backend.services.checkpoint import get_checkpoint_manager


class TaskExecutor:
    """Execute tasks through LangGraph."""

    def __init__(self):
        """Initialize task executor."""
        self.graph = office_graph
        self.checkpoint_manager = get_checkpoint_manager()
        self.active_tasks = {}

    async def execute_task(
        self,
        department: str,
        task_text: str,
        model: str = "sonnet",
        effort: str = "low",
        created_by: str = "user",
    ) -> str:
        """Execute a task through the graph.

        Returns: task_id
        """
        # Create initial state
        task_id = str(uuid.uuid4())[:8]
        current_time = time.time()

        state: OfficeState = {
            "task_id": task_id,
            "created_by": created_by,
            "created_at": current_time,
            "task_text": task_text,
            "department": department,
            "model": model,
            "effort": effort,
            "status": "pending",
            "assigned_lead": None,
            "assigned_agents": [],
            "brain_context": [],
            "brain_context_query": None,
            "messages": [],
            "working_memory": {},
            "specialist_results": {},
            "deliverable": None,
            "errors": [],
            "retry_count": 0,
            "last_error": None,
            "used_tools": [],
            "total_tokens": 0,
            "cost_usd": 0.0,
            "start_time": current_time,
            "last_checkpoint": current_time,
            "approval_status": "pending",
            "approval_feedback": None,
            "user_feedback": None,
            "version": 1,
            "checkpoint_node": None,
        }

        # Execute graph
        try:
            result = await self.graph.ainvoke(state)
            self.active_tasks[task_id] = result

            # Save checkpoint
            await self.checkpoint_manager.save_checkpoint(
                task_id, result, result.get("status", "completed")
            )

            return task_id
        except Exception as e:
            state["status"] = "failed"
            state["errors"].append(f"Execution error: {str(e)}")
            self.active_tasks[task_id] = state
            return task_id

    async def get_task_status(self, task_id: str) -> Optional[OfficeState]:
        """Get current task status."""
        if task_id in self.active_tasks:
            return self.active_tasks[task_id]

        # Try loading from checkpoint
        checkpoint = await self.checkpoint_manager.get_latest_checkpoint(task_id)
        if checkpoint:
            state, node = checkpoint
            self.active_tasks[task_id] = state
            return state

        return None

    async def approve_task(self, task_id: str, feedback: Optional[str] = None) -> bool:
        """Approve a pending task."""
        task = await self.get_task_status(task_id)
        if not task:
            return False

        task["approval_status"] = "approved"
        task["approval_feedback"] = feedback
        self.active_tasks[task_id] = task
        return True

    async def reject_task(self, task_id: str, reason: str) -> bool:
        """Reject a pending task."""
        task = await self.get_task_status(task_id)
        if not task:
            return False

        task["approval_status"] = "rejected"
        task["approval_feedback"] = reason
        self.active_tasks[task_id] = task
        return True


# Singleton instance
_task_executor = TaskExecutor()


def get_task_executor() -> TaskExecutor:
    """Get task executor instance."""
    return _task_executor
