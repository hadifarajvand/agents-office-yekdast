"""The LangGraph engine — replaces serve.mjs's route()/run()/chat().

Two call shapes, mirroring the original exactly:
  - route(dept, text, agents)   — one Haiku JSON call, picks {agent,title,plan,eta_minutes,why,needs_ok}
  - run_task(task, feedback, mode, ...) — the specialist's actual work, run through a LangGraph
    StateGraph (single "specialist" node today; the node is where a ReAct tool-calling loop over
    langchain-mcp-adapters tools plugs in once real MCP connectivity lands — mcp.py's allow/deny
    policy already gates `mcp.prompt_text()` so the specialist only ever hears about tools it may use).

The task state machine itself (next -> doing -> waiting -> done, the blocking run/revise vs.
async-ack approve/reject distinction) stays an application-level concern in main.py, exactly as
in serve.mjs, so the existing frontend's HTTP contract is untouched. LangGraph owns what happens
*inside* a single specialist turn, not the outer approval workflow.
"""
from __future__ import annotations

import re
from pathlib import Path
from typing import Optional, TypedDict

from langgraph.checkpoint.base import BaseCheckpointSaver
from langgraph.graph import END, StateGraph

from .. import brain as brainmod
from .. import learn
from .. import policy
from .. import roster as roster_mod
from ..llm import ask, ask_haiku_json, ask_with_tools
from ..mcp import registry as mcp_registry
from ..models import effort_for, model_for
from ..roster import Agent
from ..skills import Skills


def persona(a: Agent) -> str:
    lead = " (lead)" if a.lead else ""
    return f"{a.name}{lead} · {a.role} · {a.does}"


def roster_text(dept: str, agents: list[Agent]) -> str:
    return "\n".join(f"- {a.id}: {persona(a)}" for a in agents if a.department == dept)


def agent_brief(a: Agent, skills: Skills, brain_path: Path) -> str:
    parts = [a.brief or ""]
    parts.append(roster_mod.boundaries_text(a))
    parts.append(skills.prompt_text(a))
    parts.append(learn.prompt_text(brain_path, a))
    return "\n\n".join(p for p in parts if p)


def _boundary_violation(agent_boundaries: dict, call_name: str) -> str | None:
    """Task 6: a CANNOT line is prose ("Access production systems or
    infrastructure"), not a tool name, so this matches on whole significant
    words (>=4 chars) shared between the call's name and a cannot line —
    cheap, readable in the audit log, and good enough to catch an agent
    reaching for a tool its own boundaries rule out."""
    cannot = (agent_boundaries or {}).get("cannot") or []
    call_words = {w for w in re.split(r"[^a-z0-9]+", call_name.lower()) if len(w) >= 4}
    if not call_words:
        return None
    for line in cannot:
        line_words = {w for w in re.split(r"[^a-z0-9]+", line.lower()) if len(w) >= 4}
        if call_words & line_words:
            return line
    return None


def _escalation_target(agent_boundaries: dict) -> str:
    esc = (agent_boundaries or {}).get("escalation") or []
    return esc[0]["target_agent"] if esc else "the owner"


async def route(dept: str, text: str, agents: list[Agent]) -> dict:
    """The router hop — Haiku only, same output shape as serve.mjs's route()."""
    system = (
        "You route one task to the right agent in a department. Reply with JSON only: "
        '{"agent":"<id>","title":"<short title>","plan":["step1","step2"],'
        '"eta_minutes":<number>,"why":"<one line>","needs_ok":<bool>}. '
        "Pick needs_ok=true unless the task is purely read-only (listing, summarizing, reporting)."
    )
    user = f"Department roster:\n{roster_text(dept, agents)}\n\nTask: {text}"
    data = await ask_haiku_json(system, user)
    valid_ids = {a.id for a in agents if a.department == dept}
    if data.get("agent") not in valid_ids:
        data["agent"] = next((a.id for a in agents if a.department == dept and a.lead), next(iter(valid_ids), None))
    data.setdefault("title", text[:90])
    data.setdefault("plan", [])
    data.setdefault("eta_minutes", 10)
    data.setdefault("why", "")
    data.setdefault("needs_ok", True)
    return data


MAX_TOOL_STEPS = 8


class SpecialistState(TypedDict):
    system: str
    task_title: str
    task_text: str
    task_plan: list[str]
    routine_name: str
    mode: Optional[str]
    feedback: Optional[str]
    draft: str
    model_key: str
    dept: str
    agent_tools: list[str]
    agent_id: str
    agent_boundaries: dict
    brain_path: str
    result: str


def _build_user(state: SpecialistState) -> str:
    parts = [f"Task: {state['task_title']}", state["task_text"]]
    if state.get("task_plan"):
        parts.append("Plan: " + "; ".join(state["task_plan"]))
    if state.get("routine_name"):
        parts.append(f"(This is routine \"{state['routine_name']}\" firing on schedule.)")
    mode = state.get("mode")
    if mode == "draft":
        parts.append("Prepare everything but send/post/pay nothing yet — this will wait for the owner's OK.")
    elif mode == "approve":
        parts.append("The owner approved this. Carry out the outbound step now.")
        if state.get("draft"):
            parts.append(f"Previously drafted:\n{state['draft']}")
    elif mode == "routine":
        parts.append("This is read-only — report back, do not send/post/pay/change anything.")
    if state.get("feedback"):
        parts.append(f"The owner sent this feedback, revise accordingly: {state['feedback']}")
    return "\n\n".join(parts)


async def _specialist_node(state: SpecialistState) -> SpecialistState:
    """ReAct-style loop (Task 2): each iteration lets the model call a tool or
    finish. Every tool-call event is checked against mcp_registry.call_allowed()
    fresh, right before that specific call runs — never once up front for the
    whole loop — so a later step can't ride on an earlier step's authorization.
    Task 3: every call (allowed or denied) is appended to the MCP audit log,
    redacted before it's written; a tool result or exception is redacted before
    it's fed back into the conversation.

    Task 4: this node runs twice per approval round — once to draft (mode
    "draft"), once to send after the owner's OK (mode "approve") — with a
    real graph pause at the "gate" node in between, so the second pass is a
    resumption of the same thread/checkpoint rather than a fresh call."""
    dept = state.get("dept", "")
    agent_id = state.get("agent_id", "")
    brain_path = state.get("brain_path", "")
    tools = mcp_registry.tools_for(state.get("agent_tools") or [])
    tools_by_name = {t.name: t for t in tools}
    messages: list[dict] = [
        {"role": "system", "content": state["system"]},
        {"role": "user", "content": _build_user(state)},
    ]
    result = ""
    for _ in range(MAX_TOOL_STEPS):
        step = await ask_with_tools(messages, tools, model_key=state["model_key"])
        if not step["tool_calls"]:
            result = step["content"]
            break
        messages.append({"role": "assistant", "content": step["content"], "tool_calls": step["tool_calls"]})
        for call in step["tool_calls"]:
            key = mcp_registry.key_of(f'mcp__{call["name"]}__x') or call["name"]
            boundary_hit = _boundary_violation(state.get("agent_boundaries") or {}, call["name"])
            if boundary_hit:
                allowed = False
                refusal_msg = policy.refusal(
                    f'this agent\'s boundaries rule it out: "{boundary_hit}"',
                    _escalation_target(state.get("agent_boundaries") or {}),
                )
            else:
                allowed, refusal_msg = mcp_registry.call_allowed(dept, key)
            if not allowed:
                tool_result = refusal_msg
                reason = refusal_msg
            else:
                tool = tools_by_name.get(call["name"])
                reason = ""
                try:
                    tool_result = await tool.ainvoke(call["args"]) if tool else "tool not found"
                except Exception as exc:
                    tool_result = policy.redact(f"tool call failed: {exc}")
                    reason = tool_result
            tool_result = policy.redact(str(tool_result))
            if brain_path:
                policy.append_audit_log(
                    Path(brain_path),
                    policy.audit_log_line(agent_id, dept, key, call["name"], str(call["args"]), allowed, reason),
                )
            messages.append({"role": "tool", "tool_call_id": call["id"], "content": tool_result})
        result = step["content"]
    result = policy.redact(result)
    new_state = {**state, "result": result}
    if state.get("mode") == "draft":
        new_state["draft"] = result
    return new_state


async def _gate_node(state: SpecialistState) -> SpecialistState:
    """No-op node that exists only as the interrupt_before target: it marks
    the point where a "draft" pass pauses for the owner's approve/reject,
    durably, via the compiled graph's checkpointer."""
    return state


def _route_after_specialist(state: SpecialistState) -> str:
    return "gate" if state.get("mode") == "draft" else END


# Task 6's 9-stage cross-department approval workflow (from .claude/AGENTS.md),
# modeled as explicit states/transitions rather than left to prompt text. A
# task is pinned to one of these by its "stage" field (main.py's concern, same
# as next/doing/waiting/done); this module only says which moves are legal.
APPROVAL_STAGES = [
    "spec", "architecture", "data_design", "security_review",
    "code_review", "build", "staging", "production", "verify",
]


def next_approval_stage(stage: str) -> str | None:
    """The one stage allowed after `stage`, or None at the end of the chain."""
    i = APPROVAL_STAGES.index(stage)
    return APPROVAL_STAGES[i + 1] if i + 1 < len(APPROVAL_STAGES) else None


def validate_stage_transition(current: str, requested: str) -> tuple[bool, str]:
    """True + "" if `requested` is the legal next stage after `current`;
    otherwise False + a reason, so a task can't skip or go back through the
    9-stage workflow (e.g. spec -> build) or jump to an unknown stage."""
    if current not in APPROVAL_STAGES:
        return False, f'"{current}" is not one of the approval stages: {", ".join(APPROVAL_STAGES)}'
    if requested not in APPROVAL_STAGES:
        return False, f'"{requested}" is not one of the approval stages: {", ".join(APPROVAL_STAGES)}'
    expected = next_approval_stage(current)
    if requested != expected:
        return False, f'cannot move from "{current}" to "{requested}" — the next stage must be "{expected}"' if expected else f'"{current}" is the last stage — there is no next stage'
    return True, ""


_graph = StateGraph(SpecialistState)
_graph.add_node("specialist", _specialist_node)
_graph.add_node("gate", _gate_node)
_graph.set_entry_point("specialist")
_graph.add_conditional_edges("specialist", _route_after_specialist, {"gate": "gate", END: END})
_graph.add_edge("gate", "specialist")

_compiled = _graph.compile(interrupt_before=["gate"])


def compile_graph(checkpointer: BaseCheckpointSaver | None = None) -> None:
    """Recompile the module-level graph, optionally with a durable checkpointer.

    Called from main.py's startup hook once the checkpointer's Postgres
    connection is ready; the import-time compile() above keeps tests and
    any other caller that runs before startup working without one.

    Task 4 (human-in-the-loop): the plan names LangGraph's dynamic
    interrupt()/Command(resume=...) API. That API requires Python 3.11+ to
    propagate its config contextvar through an async node call (confirmed via
    direct reproduction: it raises "RuntimeError: Called get_config outside
    of a runnable context" on this project's Python 3.9 venv, root-caused to
    langgraph's ASYNCIO_ACCEPTS_CONTEXT check). The static interrupt_before
    mechanism used here — paired with aget_state/aupdate_state/ainvoke(None,
    ...) in resume_task() below — achieves the same genuine pause-and-resume
    over the durable Postgres checkpointer without that version requirement.
    """
    global _compiled
    _compiled = _graph.compile(checkpointer=checkpointer, interrupt_before=["gate"])


async def is_paused(task_id: str) -> bool:
    config = {"configurable": {"thread_id": task_id}}
    snap = await _compiled.aget_state(config)
    return bool(snap.next)


async def run_task(
    task: dict,
    feedback: str | None,
    mode: str | None,
    agent: Agent,
    agents: list[Agent],
    skills: Skills,
    brain_path: Path,
    office_model: str | None,
    office_effort: str | None,
) -> dict:
    """Mirrors serve.mjs's run(task, feedback, mode)."""
    index = brainmod.vault_index(brain_path)
    biz = brainmod.business_context(index)
    notes = brainmod.relevant_notes(index, task["dept"], task["text"])
    notes_text = brainmod.context_text(index, notes)

    system_parts = [
        f"You are {persona(agent)} at this company.",
        agent_brief(agent, skills, brain_path),
        mcp_registry.prompt_text(agent.tools),
        policy.UNTRUSTED_CONTENT_RULE,
        policy.OUTPUT_CONTRACT,
    ]
    if biz:
        system_parts.append(f"COMPANY CONTEXT\n{biz}")
    if notes_text:
        system_parts.append(f"RELEVANT NOTES\n{notes_text}")
    system = "\n\n".join(p for p in system_parts if p)

    m = model_for(task.get("model"), task.get("routineModel"), agent.model, office_model)
    e = effort_for(task.get("effort"), task.get("routineEffort"), agent.effort, office_effort, m["model"])

    config = {"configurable": {"thread_id": task.get("id", "no-task-id")}}
    out = await _compiled.ainvoke(
        {
            "system": system, "task_title": task["title"], "task_text": task["text"],
            "task_plan": task.get("plan") or [], "routine_name": task.get("routine") or "",
            "mode": mode, "feedback": feedback, "draft": task.get("draft") or "",
            "model_key": m["model"], "dept": task["dept"],
            "agent_tools": agent.tools, "agent_id": agent.id, "agent_boundaries": agent.boundaries,
            "brain_path": str(brain_path), "result": "",
        },
        config=config,
    )
    return {
        "result": out["result"],
        "skills": skills.names(agent),
        "modelUsed": m["model"], "modelFrom": m["from"],
        "effortUsed": e["effort"], "effortFrom": e["from"],
    }


async def resume_task(task_id: str, mode: str, feedback: str | None, skills: Skills, agent: Agent) -> dict:
    """Resume a graph paused at the "gate" node (Task 4): update the paused
    checkpoint's state with the owner's decision, then continue the same
    thread from that pause point — carrying forward the draft/system fields
    already in the checkpoint rather than rebuilding them from scratch.

    as_node="gate" matters: aupdate_state's default attributes the patch to
    whichever node *wrote* the pending checkpoint (here, "specialist"), which
    re-runs that node's own outgoing conditional edge against the new state
    and — since mode is no longer "draft" — routes straight to END without
    ever re-entering specialist. Attributing the update to "gate" instead
    makes it walk gate's actual edge (gate -> specialist unconditionally),
    so specialist genuinely re-executes with the owner's decision."""
    config = {"configurable": {"thread_id": task_id}}
    await _compiled.aupdate_state(config, {"mode": mode, "feedback": feedback}, as_node="gate")
    out = await _compiled.ainvoke(None, config=config)
    return {"result": out["result"], "skills": skills.names(agent)}


async def chat(agent: Agent, text: str, history: list[dict], agents: list[Agent], skills: Skills, brain_path: Path,
                office_model: str | None, office_effort: str | None) -> str:
    system = "\n\n".join(p for p in [
        f"You are {persona(agent)}, chatting with the owner.",
        agent_brief(agent, skills, brain_path),
        mcp_registry.prompt_text(agent.tools),
        policy.UNTRUSTED_CONTENT_RULE,
        policy.OUTPUT_CONTRACT,
    ] if p)
    hist_text = "\n".join(f"{h.get('role', 'owner')}: {h.get('text', '')}" for h in (history or [])[-6:])
    user = f"{hist_text}\n\nowner: {text}" if hist_text else text
    m = model_for(None, None, agent.model, office_model)
    reply = await ask(system, user, model_key=m["model"])
    return policy.redact(reply)
