"""Minimal stand-in for onboard.mjs's set-up interview.

onboard.mjs was not read/ported in full in this pass (it's a stateful multi-turn interview
flow, independent of the LangGraph/model-engine redesign). This stub keeps the /api/chat and
/api/health contracts stable — `active()` always reports no interview in progress, so chat
always falls through to normal agent chat / routine commands — rather than silently
pretending the interview feature works. Full port is tracked as follow-up work.
"""
from __future__ import annotations

from pathlib import Path


def is_set_up(brain_path: Path, dept: str) -> bool:
    return (brain_path / "Agents Office" / "agents.json").exists()


def active(data_dir: Path, dept: str) -> bool:
    return False


async def handle(*args, **kwargs):
    return None


def setup_map(brain_path: Path, depts: list[str]) -> dict:
    return {d: is_set_up(brain_path, d) for d in depts}
