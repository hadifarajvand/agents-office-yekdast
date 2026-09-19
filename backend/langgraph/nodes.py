"""LangGraph Node Implementations for Agent Office

All nodes in the orchestration graph. Each handles one step of task execution.
"""

import asyncio
import time

from backend.langgraph.state import OfficeState, Message
from backend.services.brain import rank_by_relevance, load_brain
from backend.services.roster import get_agents_by_dept

# ============ ROUTER NODE ============


async def router_node(state: OfficeState) -> OfficeState:
    """Route task to appropriate department.

    Input: task (task_id, task_text, department)
    Output: status=routed, assigned_lead
    """
    # Validate department
    agents_in_dept = get_agents_by_dept(state["department"])
    if not agents_in_dept:
        state["status"] = "failed"
        state["errors"].append(f"Department '{state['department']}' not found")
        return state

    # Find lead agent for this department
    lead_agent = next((a for a in agents_in_dept if a.get("lead")), agents_in_dept[0])

    state["assigned_lead"] = lead_agent["id"]
    state["status"] = "routed"
    state["messages"].append(
        Message(
            agent_id="router",
            role="assistant",
            content=f"Routed to {state['department']} department, lead: {lead_agent['id']}",
            timestamp=time.time(),
            tools_used=[],
        )
    )

    return state


# ============ BRAIN CONTEXT NODE ============


async def brain_context_node(state: OfficeState) -> OfficeState:
    """Retrieve relevant brain context for task.

    Input: task_text
    Output: brain_context (list of relevant notes)
    """
    brain = load_brain()

    # Simple relevance ranking on task text
    relevant_notes = rank_by_relevance(brain["all_notes"], state["task_text"], top_k=5)

    state["brain_context"] = relevant_notes
    state["brain_context_query"] = state["task_text"]
    state["messages"].append(
        Message(
            agent_id="brain",
            role="assistant",
            content=f"Retrieved {len(relevant_notes)} relevant notes from brain vault",
            timestamp=time.time(),
            tools_used=["brain"],
        )
    )

    return state


# ============ LEAD PLANNING NODE ============


async def lead_planning_node(state: OfficeState) -> OfficeState:
    """Lead agent plans approach and assigns specialists.

    Input: task_text, department, brain_context
    Output: assigned_agents, working_memory['plan']

    In Phase 2: Using simple routing. Phase 3+ will use LangChain ReAct.
    """
    from backend.langgraph.agents import DEPARTMENTS

    dept_config = DEPARTMENTS.get(state["department"])
    if not dept_config:
        state["errors"].append(f"Department config not found: {state['department']}")
        state["status"] = "failed"
        return state

    # Assign all specialists for this department (Phase 2 simple strategy)
    # Phase 3+: Lead will make selective assignments
    state["assigned_agents"] = dept_config["specialist_agents"]
    state["status"] = "planning"

    # Simple plan (Phase 2)
    plan = {
        "department": state["department"],
        "specialists_assigned": dept_config["specialist_agents"],
        "approach": "Execute all specialists in parallel, synthesize results",
        "estimated_tokens": 2500,
    }

    state["working_memory"]["plan"] = plan
    state["messages"].append(
        Message(
            agent_id=state["assigned_lead"],
            role="assistant",
            content=f"Plan: Engage {len(state['assigned_agents'])} specialists",
            timestamp=time.time(),
            tools_used=[],
        )
    )

    return state


# ============ SPECIALIST NODE (Parallel) ============


async def specialist_node(state: OfficeState, specialist_id: str) -> dict:
    """Execute a single specialist (runs in parallel).

    Input: task_text, specialist_id
    Output: specialist_results[specialist_id]

    In Phase 2: Echo placeholder. Phase 3+ integrates Claude API.
    """
    try:
        # Phase 2 Placeholder: Echo the task
        # Phase 3+: Call Claude API with system prompt + context

        result_text = (
            f"[Placeholder] {specialist_id} analyzed: {state['task_text'][:50]}..."
        )

        from backend.langgraph.state import SpecialistResult

        result: SpecialistResult = {
            "specialist_id": specialist_id,
            "success": True,
            "result": result_text,
            "error": None,
            "tokens_used": 500,
            "timestamp": time.time(),
        }

        return {"specialist_id": specialist_id, "result": result}

    except Exception as e:
        from backend.langgraph.state import SpecialistResult

        result: SpecialistResult = {
            "specialist_id": specialist_id,
            "success": False,
            "result": "",
            "error": str(e),
            "tokens_used": 100,
            "timestamp": time.time(),
        }

        return {"specialist_id": specialist_id, "result": result}


# ============ SPECIALIST EXECUTION NODE ============


async def specialist_execution_node(state: OfficeState) -> OfficeState:
    """Execute all assigned specialists in parallel.

    Input: assigned_agents, task_text
    Output: specialist_results (dict of all results)
    """
    state["status"] = "in_progress"

    # Run all specialists in parallel
    tasks = [specialist_node(state, agent_id) for agent_id in state["assigned_agents"]]

    results = await asyncio.gather(*tasks, return_exceptions=True)

    # Collect results
    for result in results:
        if isinstance(result, Exception):
            state["errors"].append(f"Specialist execution error: {str(result)}")
        else:
            specialist_id = result["specialist_id"]
            specialist_result = result["result"]
            state["specialist_results"][specialist_id] = specialist_result
            state["total_tokens"] += specialist_result["tokens_used"]

            if specialist_result["success"]:
                state["messages"].append(
                    Message(
                        agent_id=specialist_id,
                        role="assistant",
                        content=specialist_result["result"],
                        timestamp=specialist_result["timestamp"],
                        tools_used=state["used_tools"],
                    )
                )

    return state


# ============ SYNTHESIS NODE ============


async def synthesis_node(state: OfficeState) -> OfficeState:
    """Lead synthesizes specialist results into final deliverable.

    Input: specialist_results
    Output: deliverable

    In Phase 2: Simple concatenation. Phase 3+ uses LangChain aggregation.
    """
    state["status"] = "synthesis"

    # Phase 2: Simple synthesis (concatenate results)
    results_text = "\n".join(
        [
            f"[{agent_id}] {result.get('result', 'No result')}"
            for agent_id, result in state["specialist_results"].items()
        ]
    )

    state["deliverable"] = results_text
    state["working_memory"]["synthesis"] = {
        "num_specialists": len(state["specialist_results"]),
        "method": "concatenation",
    }

    state["messages"].append(
        Message(
            agent_id=state["assigned_lead"],
            role="assistant",
            content=f"Synthesized results from {len(state['specialist_results'])} specialists",
            timestamp=time.time(),
            tools_used=[],
        )
    )

    return state


# ============ BRAIN UPDATE NODE ============


async def brain_update_node(state: OfficeState) -> OfficeState:
    """Queue brain note update for this task result.

    Input: task_id, deliverable, department
    Output: working_memory['brain_update_queued'] = True

    In Phase 2: Placeholder. Phase 3+ integrates queue system.
    """
    # Phase 2: Placeholder (just track that we would update brain)
    # Phase 3+: Queue write to PostgreSQL brain_write_queue

    state["working_memory"]["brain_update"] = {
        "task_id": state["task_id"],
        "note_type": "task_result",
        "department": state["department"],
        "status": "queued",
    }

    state["messages"].append(
        Message(
            agent_id="brain",
            role="assistant",
            content=f"Brain update queued for task {state['task_id']}",
            timestamp=time.time(),
            tools_used=[],
        )
    )

    return state


# ============ APPROVAL NODE ============


async def approval_node(state: OfficeState) -> OfficeState:
    """Check approval status.

    Input: task_id, deliverable
    Output: approval_status, status=pending_approval or status=ready_for_brain_update

    In Phase 2: Auto-approve if autonomous mode, else mark pending.
    Phase 3+: Actually wait for user approval via API.
    """
    from backend.config import get_config

    config = get_config()
    autonomous_approval = config.get("autonomous_approval_mode", False)

    if autonomous_approval:
        state["approval_status"] = "approved_auto"
        state["status"] = "completed"
        state["messages"].append(
            Message(
                agent_id="orchestrator",
                role="assistant",
                content="Autonomous approval: task completed, brain updating",
                timestamp=time.time(),
                tools_used=[],
            )
        )
    else:
        state["approval_status"] = "pending"
        state["status"] = "pending_approval"
        state["messages"].append(
            Message(
                agent_id="orchestrator",
                role="assistant",
                content=f"Awaiting user approval for task {state['task_id']}",
                timestamp=time.time(),
                tools_used=[],
            )
        )

    return state


# ============ COMPLETE NODE ============


async def complete_node(state: OfficeState) -> OfficeState:
    """Mark task as completed.

    Input: task_id, deliverable, specialist_results
    Output: status=completed

    Logs final state for archival.
    """
    state["status"] = "completed"
    state["last_checkpoint"] = time.time()

    state["messages"].append(
        Message(
            agent_id="orchestrator",
            role="assistant",
            content=f"Task {state['task_id']} completed. Total tokens: {state['total_tokens']}",
            timestamp=time.time(),
            tools_used=[],
        )
    )

    return state
