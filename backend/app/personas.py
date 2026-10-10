"""Citadel personas, read from the vendored copy in seed/citadel/ (never authored here).

A persona is the whole Citadel agent file: id, name, domain, tier, tool and skill lists, the role
line, the retrieval prompt and the system prompt, kept verbatim. This module only parses them and
answers four questions: who is this persona, which department is it in, which model does its tier
resolve to, and which persona does a seat use. What a persona may *do* is decided elsewhere (the
seat's own boundaries and the pipeline); a persona file never grants a tool.
"""
from __future__ import annotations

import json
import re
from dataclasses import dataclass
from functools import lru_cache
from pathlib import Path

from .config import load_config

_ROOT = Path(__file__).resolve().parent / "seed" / "citadel"
_SEED = Path(__file__).resolve().parent / "seed" / "roster_seed.json"
# Citadel domain folder -> our department key. Only what the four live departments draw on is vendored.
DEPT_OF = {"executive": "exec", "legal": "exec", "engineering": "engineering", "security": "secdata",
           "data-analytics": "secdata", "devops": "devops", "qa-testing": "devops"}
# Tier -> model. Config key `pipeline.tiers` overrides; every tier is the one free model today.
DEFAULT_TIERS = {"reasoning_deep": "oc/big-pickle", "reasoning_fast": "oc/big-pickle",
                 "cheap_fast": "oc/big-pickle", "rag_specialist": "oc/big-pickle", "local_only": "oc/big-pickle"}


@dataclass(frozen=True)
class Persona:
    id: str
    name: str
    domain: str
    dept: str
    tier: str
    rag: bool
    tools: tuple[str, ...]
    skills: tuple[str, ...]
    role: str
    system_prompt: str
    rag_prompt: str
    source: str  # path under seed/citadel


@dataclass(frozen=True)
class HandAgent:
    """One of Citadel's 11 hand-written Claude Code subagents: a real tool allowlist and a prompt."""
    id: str
    description: str
    tools: tuple[str, ...]
    permission_mode: str
    body: str
    source: str


def _frontmatter(text: str) -> tuple[dict, str]:
    m = re.match(r"---\n(.*?)\n---\n?(.*)", text, re.S)
    if not m:
        return {}, text
    meta: dict = {}
    for line in m.group(1).splitlines():
        k, _, v = line.partition(":")
        meta[k.strip()] = v.strip()
    return meta, m.group(2)


def _list(v: str) -> tuple[str, ...]:
    return tuple(x.strip().strip("'\"") for x in v.strip().strip("[]").split(",") if x.strip())


def _section(body: str, title: str) -> str:
    m = re.search(rf"^## {re.escape(title)}\n(.*?)(?=^## |\Z)", body, re.S | re.M)
    return m.group(1).strip() if m else ""


@lru_cache(maxsize=1)
def _load() -> tuple[dict[str, Persona], dict[str, HandAgent]]:
    people: dict[str, Persona] = {}
    for domain, dept in DEPT_OF.items():
        for p in sorted((_ROOT / "agents" / domain).glob("*.md")):
            meta, body = _frontmatter(p.read_text())
            pid = meta.get("id") or p.stem
            people[pid] = Persona(
                id=pid, name=meta.get("name", pid), domain=domain, dept=dept, tier=meta.get("tier", "reasoning_fast"),
                rag=meta.get("rag_enabled", "false").lower() == "true", tools=_list(meta.get("tools", "[]")),
                skills=_list(meta.get("skills", "[]")), role=_section(body, "Role"),
                system_prompt=_section(body, "LLM System Prompt"), rag_prompt=_section(body, "RAG Retrieval Prompt"),
                source=str(p.relative_to(_ROOT)))
    hands: dict[str, HandAgent] = {}
    for p in sorted((_ROOT / "agents" / "hand").glob("*.md")):
        meta, body = _frontmatter(p.read_text())
        hid = meta.get("name") or p.stem
        hands[hid] = HandAgent(id=hid, description=meta.get("description", ""), tools=_list(meta.get("tools", "[]")),
                               permission_mode=meta.get("permissionMode", ""), body=body.strip(),
                               source=str(p.relative_to(_ROOT)))
    return people, hands


def get(persona_id: str) -> Persona | None:
    return _load()[0].get(persona_id)


def all_personas(dept: str | None = None) -> list[Persona]:
    return [p for p in _load()[0].values() if dept is None or p.dept == dept]


def hand_agents() -> list[HandAgent]:
    return list(_load()[1].values())


@lru_cache(maxsize=1)
def _seat_ids() -> dict[str, str]:
    """seat id -> Citadel id, from the `Citadel: <id>` line each seed tagline already carries."""
    out: dict[str, str] = {}
    for row in json.loads(_SEED.read_text()).get("v1", []):
        m = re.search(r"Citadel: ([\w-]+)", row.get("tagline", ""))
        if m:
            out[row["id"]] = m.group(1)
    return out


def for_seat(seat_id: str) -> Persona | None:
    cid = _seat_ids().get(seat_id) or seat_id  # a lead's seat id is its Citadel id
    return get(cid)


def model_for(tier: str) -> str:
    tiers = {**DEFAULT_TIERS, **(load_config().pipeline.get("tiers") or {})}
    return tiers.get(tier) or tiers["reasoning_fast"]
