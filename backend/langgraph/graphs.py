"""StateGraph definitions for Agent Office

Builds the execution graph using LangGraph.
"""

from langgraph.graph import StateGraph, END
from backend.langgraph.state import OfficeState
from backend.langgraph.nodes import (
    router_node,
    brain_context_node,
    lead_planning_node,
    specialist_execution_node,
    synthesis_node,
    brain_update_node,
    approval_node,
    complete_node,
)


def create_office_graph():
    """Create the main task execution graph.

    Flow:
    router → brain_context → lead_planning → specialist_execution
    → synthesis → brain_update → approval → complete
    """

    # Create graph
    graph = StateGraph(OfficeState)

    # Add nodes
    graph.add_node("router", router_node)
    graph.add_node("brain_context", brain_context_node)
    graph.add_node("lead_planning", lead_planning_node)
    graph.add_node("specialist_execution", specialist_execution_node)
    graph.add_node("synthesis", synthesis_node)
    graph.add_node("brain_update", brain_update_node)
    graph.add_node("approval", approval_node)
    graph.add_node("complete", complete_node)

    # Add edges (linear flow for Phase 2)
    graph.add_edge("router", "brain_context")
    graph.add_edge("brain_context", "lead_planning")
    graph.add_edge("lead_planning", "specialist_execution")
    graph.add_edge("specialist_execution", "synthesis")
    graph.add_edge("synthesis", "brain_update")
    graph.add_edge("brain_update", "approval")

    # Conditional: approval status
    def approval_router(state: OfficeState):
        if state["status"] == "completed":
            return "complete"
        else:
            # Pending approval - stays in pending_approval state
            # API will update and resume from approval node
            return END

    graph.add_conditional_edges(
        "approval",
        approval_router,
        {"complete": "complete", "__end__": END},
    )
    graph.add_edge("complete", END)

    # Set entry point
    graph.set_entry_point("router")

    # Compile graph
    return graph.compile()


def create_department_graph(department: str):
    """Create a department-specific sub-graph (Phase 3+).

    For now, all departments use the main graph.
    Phase 3+ can create specialized graphs per department.
    """
    return create_office_graph()


# Instantiate main graph
office_graph = create_office_graph()
