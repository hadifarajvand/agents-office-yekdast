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

from pathlib import Path
from typing import TypedDict

from langgraph.checkpoint.base import BaseCheckpointSaver
from langgraph.graph import END, StateGraph

from .. import brain as brainmod
from .. import learn
from .. import policy
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
    parts.append(skills.prompt_text(a))
    parts.append(learn.prompt_text(brain_path, a))
    return "\n\n".join(p for p in parts if p)


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
    user: str
    model_key: str
    dept: str
    agent_tools: list[str]
    agent_id: str
    brain_path: str
    result: str


async def _specialist_node(state: SpecialistState) -> SpecialistState:
    """ReAct-style loop (Task 2): each iteration lets the model call a tool or
    finish. Every tool-call event is checked against mcp_registry.call_allowed()
    fresh, right before that specific call runs — never once up front for the
    whole loop — so a later step can't ride on an earlier step's authorization.
    Task 3: every call (allowed or denied) is appended to the MCP audit log,
    redacted before it's written; a tool result or exception is redacted before
    it's fed back into the conversation."""
    dept = state.get("dept", "")
    agent_id = state.get("agent_id", "")
    brain_path = state.get("brain_path", "")
    tools = mcp_registry.tools_for(state.get("agent_tools") or [])
    tools_by_name = {t.name: t for t in tools}
    messages: list[dict] = [
        {"role": "system", "content": state["system"]},
        {"role": "user", "content": state["user"]},
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
    return {**state, "result": policy.redact(result)}


_graph = StateGraph(SpecialistState)
_graph.add_node("specialist", _specialist_node)
_graph.set_entry_point("specialist")
_graph.add_edge("specialist", END)

_compiled = _graph.compile()


def compile_graph(checkpointer: BaseCheckpointSaver | None = None) -> None:
    """Recompile the module-level graph, optionally with a durable checkpointer.

    Called from main.py's startup hook once the checkpointer's Postgres
    connection is ready; the import-time compile() above keeps tests and
    any other caller that runs before startup working without one.
    """
    global _compiled
    _compiled = _graph.compile(checkpointer=checkpointer)


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

    user_parts = [f"Task: {task['title']}", task["text"]]
    if task.get("plan"):
        user_parts.append("Plan: " + "; ".join(task["plan"]))
    if task.get("routine"):
        user_parts.append(f"(This is routine \"{task['routine']}\" firing on schedule.)")
    if mode == "draft":
        user_parts.append("Prepare everything but send/post/pay nothing yet — this will wait for the owner's OK.")
    elif mode == "approve":
        user_parts.append("The owner approved this. Carry out the outbound step now.")
        if task.get("draft"):
            user_parts.append(f"Previously drafted:\n{task['draft']}")
    elif mode == "routine":
        user_parts.append("This is read-only — report back, do not send/post/pay/change anything.")
    if feedback:
        user_parts.append(f"The owner sent this feedback, revise accordingly: {feedback}")
    user = "\n\n".join(user_parts)

    m = model_for(task.get("model"), task.get("routineModel"), agent.model, office_model)
    e = effort_for(task.get("effort"), task.get("routineEffort"), agent.effort, office_effort, m["model"])

    config = {"configurable": {"thread_id": task.get("id", "no-task-id")}}
    out = await _compiled.ainvoke(
        {
            "system": system, "user": user, "model_key": m["model"], "dept": task["dept"],
            "agent_tools": agent.tools, "agent_id": agent.id, "brain_path": str(brain_path), "result": "",
        },
        config=config,
    )
    return {
        "result": out["result"],
        "skills": skills.names(agent),
        "modelUsed": m["model"], "modelFrom": m["from"],
        "effortUsed": e["effort"], "effortFrom": e["from"],
    }


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
