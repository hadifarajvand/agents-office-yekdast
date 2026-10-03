"""Port of learn.mjs — the agents learn from your corrections.

Every time a deliverable is sent back ("revise: …"), the correction is written to
<brain>/Agents Office/feedback/<agent-id>.md, sorted into a one-off or a standing rule.
Standing rules are read by that agent before every task and chat turn.
"""
from __future__ import annotations

import json
import re
from datetime import date
from pathlib import Path
from typing import Awaitable, Callable

MAX_RULES = 15


def dir_(brain_path: Path) -> Path:
    return brain_path / "Agents Office" / "feedback"


def _file(brain_path: Path, agent_id: str) -> Path:
    return dir_(brain_path) / f"{agent_id}.md"


def _head(agent) -> str:
    return (
        f"# Corrections for {agent.name} ({agent.id})\n\n"
        "Every time the owner sends this agent's work back, the correction lands here. Lines under\n"
        '"Standing rules" are read by this agent before every task and chat turn. Edit freely: reword a\n'
        "rule, delete a line to unlearn it, move a one-off up to make it a rule. When a rule is really a\n"
        "process, put it in a skill (SKILLS.md).\n\n## Standing rules\n\n## One-offs\n"
    )


def read(brain_path: Path, agent_id: str) -> dict:
    p = _file(brain_path, agent_id)
    if not p.exists():
        return {"rules": [], "oneOffs": []}
    out: dict = {"rules": [], "oneOffs": []}
    sec = None
    for line in p.read_text().splitlines():
        if re.match(r"^##\s+standing rules", line, re.IGNORECASE):
            sec = "rules"
            continue
        if re.match(r"^##\s+one-offs", line, re.IGNORECASE):
            sec = "oneOffs"
            continue
        if re.match(r"^##?\s", line):
            sec = None
            continue
        m = re.match(r"^\s*[-*]\s+(.+)$", line)
        if m and sec:
            out[sec].append(m.group(1).strip())
    return out


def record(brain_path: Path, agent, task, feedback: str, verdict: dict | None) -> dict:
    dir_(brain_path).mkdir(parents=True, exist_ok=True)
    p = _file(brain_path, agent.id)
    text = p.read_text() if p.exists() else _head(agent)
    if not re.search(r"^## Standing rules", text, re.MULTILINE):
        text += "\n## Standing rules\n"
    if not re.search(r"^## One-offs", text, re.MULTILINE):
        text += "\n## One-offs\n"

    d = date.today().isoformat()
    quote = re.sub(r"\s+", " ", str(feedback)).strip()[:160]
    ctx = f" ({str(task.get('title'))[:60]})" if task and task.get("title") else ""
    standing = bool(verdict and verdict.get("standing") and verdict.get("rule"))
    if standing:
        rule = re.sub(r"\s+", " ", str(verdict["rule"])).strip()[:240]
        line = f'- {d} · {rule} ← "{quote}"{ctx}'
    else:
        line = f'- {d} · "{quote}"{ctx}'

    insert_after = re.compile(r"^## Standing rules[^\n]*\n", re.MULTILINE) if standing else re.compile(r"^## One-offs[^\n]*\n", re.MULTILINE)
    m = insert_after.search(text)
    start = m.end()
    rest = text[start:]
    next_m = re.search(r"^## ", rest, re.MULTILINE)
    end = len(text) if next_m is None else start + next_m.start()
    after = text[end:]
    before = re.sub(r"\s*$", "\n", text[:end])
    text = before + line + "\n" + ("\n" if after and not after.startswith("\n") else "") + after

    p.write_text(text)
    return {"standing": standing, "line": line, "path": str(p)}


async def classify(ask: Callable[..., Awaitable[str]], agent, task, feedback: str) -> dict | None:
    system = "You sort an owner's feedback on an AI agent's work. Return ONLY a JSON object, no prose, no code fences."
    user = (
        f"Agent: {agent.name} — {agent.role}. {agent.does}\n"
        f"Task: {task.get('title', '') if task else ''}\n"
        f'Owner\'s feedback: "{feedback}"\n\n'
        'Is this a ONE-OFF (about this task, this client, this draft only) or a STANDING RULE '
        "(a preference the owner will want applied to every future piece of this kind of work)?\n"
        'Signals of a standing rule: "always", "never", "from now on", "we don\'t", a format or tone '
        'preference, a red line. Signals of a one-off: a fact about this client, a change to this draft '
        'only, "this time", "here".\n'
        'Return: {"standing": true|false, "rule": "<if standing: the preference as ONE short imperative '
        'sentence, general, no client or project names; else empty string>"}'
    )
    try:
        raw = await ask(system, user, max_tokens=200)
        j = json.loads(re.sub(r"```json|```", "", raw).strip())
        return {"standing": bool(j.get("standing")) and bool(j.get("rule")), "rule": str(j.get("rule", "")).strip()}
    except Exception:
        return None


def prompt_text(brain_path: Path, agent) -> str:
    rules = read(brain_path, agent.id)["rules"]
    if not rules:
        return ""
    recent = [
        "- " + re.sub(r'\s*←\s*".*$', "", re.sub(r"^\d{4}-\d{2}-\d{2}\s*·\s*", "", r))
        for r in rules[-MAX_RULES:]
    ]
    return "LESSONS — what the owner corrected before. Apply every one of these, every time, without being asked:\n" + "\n".join(recent)


def count(brain_path: Path, agent_id: str) -> int:
    return len(read(brain_path, agent_id)["rules"])
