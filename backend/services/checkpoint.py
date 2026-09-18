"""PostgreSQL state checkpointing for LangGraph tasks

Save/load OfficeState snapshots for recovery on restart.
"""

import time
from typing import Optional

from backend.langgraph.state import OfficeState


class CheckpointManager:
    """Manage task state checkpoints in PostgreSQL."""

    def __init__(self):
        """Initialize checkpoint manager (uses in-memory for Phase 2)."""
        # Phase 2: In-memory checkpoint store
        # Phase 3: Replace with PostgreSQL
        self.checkpoints = {}

    async def save_checkpoint(
        self, task_id: str, state: OfficeState, node_name: str
    ) -> bool:
        """Save state checkpoint at critical node."""
        try:
            checkpoint = {
                "task_id": task_id,
                "node_name": node_name,
                "timestamp": time.time(),
                "state": self._serialize_state(state),
            }
            self.checkpoints[f"{task_id}:{node_name}"] = checkpoint
            return True
        except Exception as e:
            print(f"[ERROR] Failed to save checkpoint: {e}")
            return False

    async def load_checkpoint(
        self, task_id: str, node_name: str
    ) -> Optional[OfficeState]:
        """Load state checkpoint from specific node."""
        try:
            key = f"{task_id}:{node_name}"
            if key not in self.checkpoints:
                return None
            checkpoint = self.checkpoints[key]
            return self._deserialize_state(checkpoint["state"])
        except Exception as e:
            print(f"[ERROR] Failed to load checkpoint: {e}")
            return None

    async def get_latest_checkpoint(self, task_id: str) -> Optional[tuple]:
        """Get latest checkpoint for task (state, node_name)."""
        try:
            matching = [
                (v, k.split(":")[1])
                for k, v in self.checkpoints.items()
                if k.startswith(f"{task_id}:")
            ]
            if not matching:
                return None
            latest = max(matching, key=lambda x: x[0]["timestamp"])
            return (self._deserialize_state(latest[0]["state"]), latest[1])
        except Exception as e:
            print(f"[ERROR] Failed to get latest checkpoint: {e}")
            return None

    def _serialize_state(self, state: OfficeState) -> dict:
        """Convert OfficeState to JSON-serializable dict."""
        return {
            "task_id": state["task_id"],
            "status": state["status"],
            "assigned_lead": state["assigned_lead"],
            "assigned_agents": state["assigned_agents"],
            "deliverable": state["deliverable"],
            "errors": state["errors"],
            "total_tokens": state["total_tokens"],
            "cost_usd": state["cost_usd"],
        }

    def _deserialize_state(self, data: dict) -> OfficeState:
        """Restore OfficeState from dict (Phase 2 minimal)."""
        # Phase 2: Return minimal restored state
        # Phase 3: Restore full state with all fields
        return {
            "task_id": data["task_id"],
            "created_by": "checkpoint_restore",
            "created_at": time.time(),
            "task_text": "",
            "department": "",
            "model": "",
            "effort": "",
            "status": data["status"],
            "assigned_lead": data["assigned_lead"],
            "assigned_agents": data["assigned_agents"],
            "brain_context": [],
            "brain_context_query": None,
            "messages": [],
            "working_memory": {},
            "specialist_results": {},
            "deliverable": data["deliverable"],
            "errors": data["errors"],
            "retry_count": 0,
            "last_error": None,
            "used_tools": [],
            "total_tokens": data["total_tokens"],
            "cost_usd": data["cost_usd"],
            "start_time": time.time(),
            "last_checkpoint": time.time(),
            "approval_status": "pending",
            "approval_feedback": None,
            "user_feedback": None,
            "version": 1,
            "checkpoint_node": None,
        }


# Singleton instance
_checkpoint_manager = CheckpointManager()


def get_checkpoint_manager() -> CheckpointManager:
    """Get checkpoint manager instance."""
    return _checkpoint_manager
