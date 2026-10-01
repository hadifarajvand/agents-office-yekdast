"""Port of config.mjs — office.config.json <- office.config.local.json <- env vars."""
from __future__ import annotations

import json
import os
from dataclasses import dataclass, field
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]

DEFAULTS = {
    "name": "Agents Office",
    "brain": "./brain",
    "port": 4520,
    "model": "sonnet",
    "mcp": {"allow": [], "deny": [], "departments": {}},
    "tools": {"web": True},
}


def _read_json(path: Path) -> dict:
    try:
        return json.loads(path.read_text())
    except (FileNotFoundError, json.JSONDecodeError):
        return {}


@dataclass
class Config:
    name: str
    brain: str
    port: int
    model: str
    mcp: dict
    tools: dict
    brain_path: Path


def load_config() -> Config:
    base = _read_json(ROOT / "office.config.json")
    local = _read_json(ROOT / "office.config.local.json")
    merged = {**DEFAULTS, **base, **local}

    merged["name"] = os.environ.get("AO_NAME", merged["name"])
    merged["brain"] = os.environ.get("AO_BRAIN", merged["brain"])
    merged["port"] = int(os.environ.get("PORT", merged["port"]))
    merged["model"] = os.environ.get("AO_MODEL", merged["model"])

    mcp = {**DEFAULTS["mcp"], **(base.get("mcp") or {}), **(local.get("mcp") or {})}
    tools = {**DEFAULTS["tools"], **(base.get("tools") or {}), **(local.get("tools") or {})}

    brain_path = Path(merged["brain"])
    if not brain_path.is_absolute():
        brain_path = (ROOT / brain_path).resolve()

    return Config(
        name=merged["name"],
        brain=merged["brain"],
        port=merged["port"],
        model=merged["model"],
        mcp=mcp,
        tools=tools,
        brain_path=brain_path,
    )
