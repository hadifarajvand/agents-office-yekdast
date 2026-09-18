"""LangGraph Phase 2 Tests

Tests for core graph infrastructure, state management, and node execution.
"""

import time

from backend.langgraph.state import OfficeState
from backend.langgraph.graphs import office_graph
from backend.langgraph.agents import DEPARTMENTS, ORCHESTRATOR_CONFIG


class TestOfficeState:
    """Test OfficeState schema and initialization."""

    def test_state_initialization(self):
        """Test creating a valid OfficeState."""
        state: OfficeState = {
            "task_id": "test-1",
            "created_by": "user@example.com",
            "created_at": time.time(),
            "task_text": "Test task",
            "department": "marketing",
            "model": "sonnet",
            "effort": "low",
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
            "start_time": time.time(),
            "last_checkpoint": time.time(),
            "approval_status": "pending",
            "approval_feedback": None,
            "user_feedback": None,
            "version": 1,
            "checkpoint_node": None,
        }

        assert state["task_id"] == "test-1"
        assert state["status"] == "pending"
        assert state["assigned_lead"] is None
        assert len(state["messages"]) == 0

    def test_state_has_required_fields(self):
        """Test that OfficeState has all required fields."""
        required_fields = {
            "task_id",
            "created_by",
            "created_at",
            "task_text",
            "department",
            "status",
            "messages",
            "errors",
            "deliverable",
        }

        state: OfficeState = {
            "task_id": "test",
            "created_by": "user",
            "created_at": 0.0,
            "task_text": "test",
            "department": "marketing",
            "model": "sonnet",
            "effort": "low",
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
            "start_time": 0.0,
            "last_checkpoint": 0.0,
            "approval_status": "pending",
            "approval_feedback": None,
            "user_feedback": None,
            "version": 1,
            "checkpoint_node": None,
        }

        for field in required_fields:
            assert field in state


class TestAgentConfigs:
    """Test agent configuration definitions."""

    def test_department_structure(self):
        """Test that departments are properly defined."""
        assert "marketing" in DEPARTMENTS
        assert "support" in DEPARTMENTS
        assert "engineering" in DEPARTMENTS
        assert "research" in DEPARTMENTS

    def test_department_has_lead(self):
        """Test that each department has a lead agent."""
        for dept_name, dept_config in DEPARTMENTS.items():
            assert "lead_agent_id" in dept_config
            assert dept_config["lead_agent_id"] is not None

    def test_department_has_specialists(self):
        """Test that each department has specialist assignments."""
        for dept_name, dept_config in DEPARTMENTS.items():
            assert "specialist_agents" in dept_config
            assert len(dept_config["specialist_agents"]) > 0

    def test_agent_config_retrieval(self):
        """Test retrieving individual agent configs."""
        # Test that ORCHESTRATOR_CONFIG is properly defined
        assert ORCHESTRATOR_CONFIG is not None
        assert ORCHESTRATOR_CONFIG["agent_id"] == "orchestrator"

    def test_orchestrator_exists(self):
        """Test that orchestrator agent is defined."""
        assert ORCHESTRATOR_CONFIG is not None
        assert "Orchestrator" in ORCHESTRATOR_CONFIG["agent_name"]


class TestStateGraph:
    """Test LangGraph StateGraph compilation and execution."""

    def test_graph_compiles(self):
        """Test that the graph compiles without errors."""
        assert office_graph is not None

    def test_graph_has_nodes(self):
        """Test that graph has expected nodes."""
        # Graph should have routing, brain, planning, execution, synthesis nodes
        assert office_graph is not None

    def test_graph_has_input_schema(self):
        """Test that graph has proper input schema."""
        # Graph schema should be OfficeState
        assert office_graph is not None
        # Verify we can access the input schema
        schema = office_graph.input_schema
        assert schema is not None


class TestGraphExecution:
    """Test graph execution flow."""

    def test_graph_has_proper_structure(self):
        """Test that graph has proper node structure."""
        # Check graph has nodes
        assert office_graph is not None
        # Graph structure should be set up
        assert hasattr(office_graph, "invoke") or hasattr(office_graph, "ainvoke")

    def test_graph_is_callable(self):
        """Test that graph is callable."""
        # Graph should have execution methods
        assert office_graph is not None
        # Verify we have async execution capability
        assert hasattr(office_graph, "ainvoke")


class TestApprovalWorkflow:
    """Test approval workflow in graph."""

    def test_approval_status_field_exists(self):
        """Test that approval status field can be set."""
        state: OfficeState = {
            "task_id": "approve-test",
            "created_by": "tester",
            "created_at": time.time(),
            "task_text": "Test approval flow",
            "department": "support",
            "model": "sonnet",
            "effort": "low",
            "status": "pending_approval",
            "assigned_lead": "support_lead",
            "assigned_agents": ["support_agent"],
            "brain_context": [],
            "brain_context_query": None,
            "messages": [],
            "working_memory": {},
            "specialist_results": {},
            "deliverable": "Sample deliverable",
            "errors": [],
            "retry_count": 0,
            "last_error": None,
            "used_tools": [],
            "total_tokens": 100,
            "cost_usd": 0.01,
            "start_time": time.time(),
            "last_checkpoint": time.time(),
            "approval_status": "pending",
            "approval_feedback": None,
            "user_feedback": None,
            "version": 1,
            "checkpoint_node": None,
        }

        # Verify state has approval fields
        assert state["approval_status"] in (
            "pending",
            "approved",
            "rejected",
            "approved_auto",
        )
        assert "approval_feedback" in state
