"""Port of src/models.js — the four agent-facing models, by name.

Haiku is the office default for everything an agent does except where sonnet or opus
is explicitly pinned (task beats routine beats agent beats office default, same
four-place precedence as before). This reverses the project's former "never haiku for
agent-facing work" guardrail — that rule, and the roster-validation rejection of
"haiku" as a selectable agent/task model, were removed by explicit owner instruction
(2026-10-03) to cut cost across the 35-seat roster for testing. Haiku is also still
used, unconditionally, for the internal Router node (backend/app/graph/router.py).
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
    "haiku": ModelDef("haiku", "Haiku", "haiku", os.environ.get("ANTHROPIC_DEFAULT_HAIKU_MODEL", "claude-haiku-4-5-20251001")),
}
MODEL_KEYS = ["sonnet", "opus", "fable", "haiku"]
DEFAULT_MODEL = "haiku"
EFFORT_KEYS = ["low", "medium", "high", "xhigh", "max"]
EFFORT_NAME = {"low": "Low", "medium": "Medium", "high": "High", "xhigh": "X-high", "max": "Max"}

# Kept as an alias for the internal Router node (backend/app/graph/router.py), which
# pins Haiku regardless of office/agent config.
HAIKU_MODEL_ID = MODELS["haiku"].id


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
