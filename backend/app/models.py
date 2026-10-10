"""Office model keys (the four names in the task/agent/routine menus) and which one wins.

A key is resolved to the model id the 9router proxy expects through
`office.config.json` -> router.models (override one with ROUTER_MODEL_<KEY>, e.g.
ROUTER_MODEL_HAIKU). Pipeline roles (builder, research, lead review...) do not use
these keys; they are pinned to router ids in config.roles (see llm.role_model).

Precedence for a task: task beats routine beats agent beats office, then the
office default (Haiku, owner decision 2026-10-03).
"""
from __future__ import annotations

import os
import re
from dataclasses import dataclass

from .config import load_config


@dataclass(frozen=True)
class ModelDef:
    key: str
    name: str
    effort: str | None = None


MODELS: dict[str, ModelDef] = {
    "sonnet": ModelDef("sonnet", "Sonnet"),
    "opus": ModelDef("opus", "Opus", effort="high"),
    "fable": ModelDef("fable", "Fable"),
    "haiku": ModelDef("haiku", "Haiku"),
}
MODEL_KEYS = ["sonnet", "opus", "fable", "haiku"]
DEFAULT_MODEL = "haiku"
EFFORT_KEYS = ["low", "medium", "high", "xhigh", "max"]
EFFORT_NAME = {"low": "Low", "medium": "Medium", "high": "High", "xhigh": "X-high", "max": "Max"}


_ROUTER_ID = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._-]*/[A-Za-z0-9][A-Za-z0-9._:/@-]{0,127}$")


def is_router_id(s: str | None) -> bool:
    """Any model the router serves, written provider/name (cc/..., oc/..., kr/...)."""
    return bool(s) and bool(_ROUTER_ID.match(str(s).strip()))


def model_id(k: str | None) -> str:
    """Router model id for an office key. A router id passes through unchanged;
    other unknown keys fall back to the default."""
    if is_router_id(k):
        return str(k).strip()
    key = k if k in MODELS else DEFAULT_MODEL
    env = os.environ.get(f"ROUTER_MODEL_{key.upper()}")
    if env:
        return env
    return load_config().router.get("models", {}).get(key) or key


HAIKU_MODEL_ID = model_id("haiku")


def norm_effort(s: str | None) -> str | None:
    t = re.sub(r"[\s_-]+", "", str(s or "")).lower().strip()
    if not t or t in ("auto", "default"):
        return None
    if t in ("extrahigh", "veryhigh"):
        return "xhigh"
    if t == "maximum":
        return "max"
    return t if t in EFFORT_KEYS else None


def norm_model(s: str | None) -> str | None:
    """Exact match on a key or on the router id a key maps to. No substring
    matching: "sonnet-evil" is not "sonnet"."""
    t = str(s or "").lower().strip()
    if not t:
        return None
    if t in MODELS:
        return t
    for k in MODEL_KEYS:
        if t == model_id(k).lower():
            return k
    raw = str(s).strip()
    return raw if is_router_id(raw) else None


def effort_for(task=None, routine=None, agent=None, office=None, model=None) -> dict:
    for src_name, src in (("task", task), ("routine", routine), ("agent", agent), ("office", office)):
        e = norm_effort(src)
        if e:
            return {"effort": e, "from": src_name}
    m = MODELS.get(norm_model(model) or "", MODELS[DEFAULT_MODEL])
    return {"effort": m.effort, "from": "model"}


def model_for(task=None, routine=None, agent=None, office=None) -> dict:
    for src_name, src in (("task", task), ("routine", routine), ("agent", agent)):
        m = norm_model(src)
        if m:
            return {"model": m, "from": src_name}
    return {"model": norm_model(office) or DEFAULT_MODEL, "from": "office"}
