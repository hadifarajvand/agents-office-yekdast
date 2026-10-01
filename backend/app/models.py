"""Port of src/models.js — the three agent-facing models, by name.

Sonnet is the office default for everything an agent does, including (today) routing.
Effort lives inside the name (Opus runs at high); same four-place precedence everywhere:
task beats routine beats agent beats office default.

HAIKU_MODEL_ID below is NOT part of this public model selection. It exists only for the
internal Router node (backend/app/graph/router.py), which classifies a task to a
department/agent and is deliberately pinned to Haiku for cost/speed — see
.claude/LANGGRAPH-MIGRATION-PLAN.md and the approved redesign plan for why this one hop
is the sanctioned exception to "never haiku".
"""
from __future__ import annotations

import os
import re
from dataclasses import dataclass


@dataclass(frozen=True)
class ModelDef:
    key: str
    name: str
    flag: str
    id: str
    effort: str | None = None


MODELS: dict[str, ModelDef] = {
    "sonnet": ModelDef("sonnet", "Sonnet", "sonnet", os.environ.get("ANTHROPIC_DEFAULT_SONNET_MODEL", "claude-sonnet-5")),
    "opus": ModelDef("opus", "Opus", "opus", os.environ.get("ANTHROPIC_DEFAULT_OPUS_MODEL", "claude-opus-5"), effort="high"),
    "fable": ModelDef("fable", "Fable", "fable", os.environ.get("ANTHROPIC_DEFAULT_FABLE_MODEL", "claude-fable-5-1")),
}
MODEL_KEYS = ["sonnet", "opus", "fable"]
DEFAULT_MODEL = "sonnet"
EFFORT_KEYS = ["low", "medium", "high", "xhigh", "max"]
EFFORT_NAME = {"low": "Low", "medium": "Medium", "high": "High", "xhigh": "X-high", "max": "Max"}

# Internal-only — never selectable via task/routine/agent/office config, never exposed to check.mjs-style
# roster validation (which must keep rejecting "haiku" as an agent/task model, per .claude/*.md).
HAIKU_MODEL_ID = os.environ.get("ANTHROPIC_DEFAULT_HAIKU_MODEL", "claude-haiku-4-5-20251001")


def norm_effort(s: str | None) -> str | None:
    t = re.sub(r"[\s_-]+", "", str(s or "")).lower().strip()
    if not t or t in ("auto", "default"):
        return None
    if t in ("extrahigh", "veryhigh"):
        return "xhigh"
    if t == "maximum":
        return "max"
    return t if t in EFFORT_KEYS else None


def effort_name(k: str | None) -> str:
    return EFFORT_NAME.get(k or "", "Auto")


def effort_for(task=None, routine=None, agent=None, office=None, model=None) -> dict:
    for src_name, src in (("task", task), ("routine", routine), ("agent", agent), ("office", office)):
        e = norm_effort(src)
        if e:
            return {"effort": e, "from": src_name}
    m = MODELS.get(norm_model(model) or "", MODELS[DEFAULT_MODEL])
    return {"effort": m.effort, "from": "model"}


def norm_model(s: str | None) -> str | None:
    t = str(s or "").lower().strip()
    if not t:
        return None
    for k in MODEL_KEYS:
        if t == k or k in t:
            return k
    return None


def model_name(k: str | None) -> str:
    return MODELS.get(k or "", MODELS[DEFAULT_MODEL]).name


def model_id(k: str | None) -> str:
    return MODELS.get(k or "", MODELS[DEFAULT_MODEL]).id


def model_for(task=None, routine=None, agent=None, office=None) -> dict:
    for src_name, src in (("task", task), ("routine", routine), ("agent", agent)):
        m = norm_model(src)
        if m:
            return {"model": m, "from": src_name}
    return {"model": norm_model(office) or DEFAULT_MODEL, "from": "office"}
