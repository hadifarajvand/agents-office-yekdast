"""Which departments are "set up": a department counts as set up once the owner has
given at least one of its agents a brief or bound a skill to it.

The multi-turn set-up interview of the original Node office (onboard.mjs) is not part
of this platform; `active()` always reports no interview in progress, so chat falls
through to normal agent chat.
"""
from __future__ import annotations

from pathlib import Path


def is_set_up(dept: str, agents: list | None = None, skills=None) -> bool:
    mine = [a for a in (agents or []) if a.department == dept]
    if any(getattr(a, "brief", "") for a in mine):
        return True
    if skills is not None:
        return any(skills.for_agent(a) and any(not s.everyone for s in skills.for_agent(a)) for a in mine)
    return False


def active(data_dir: Path, dept: str) -> bool:
    return False


def setup_map(depts: list[str], agents: list | None = None, skills=None) -> dict:
    return {d: is_set_up(d, agents, skills) for d in depts}
