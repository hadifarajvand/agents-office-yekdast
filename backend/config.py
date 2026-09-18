"""Configuration loader (adapts config.mjs)

Loads office.config.json → office.config.local.json → environment variables
Pattern: later overwrites earlier, env vars override all
"""

import json
import os
from pathlib import Path
from typing import Dict, Any

ROOT = Path(__file__).parent.parent


def read_json(path: Path) -> Dict[str, Any]:
    """Safely read JSON file, return {} if not found"""
    try:
        return json.loads(path.read_text())
    except (FileNotFoundError, json.JSONDecodeError):
        return {}


def load_config() -> Dict[str, Any]:
    """Load config from files + environment"""

    # Base defaults
    base = read_json(ROOT / "office.config.json")
    local = read_json(ROOT / "office.config.local.json")

    # Merge: shipped → local → env
    config = {
        "name": "Agents Office",
        "brain": "./brain",
        "port": 8000,  # Python backend (v3.6 frontend stays on 4520)
        "model": "sonnet",  # sonnet | opus | fable
        "timeout": 300,  # seconds per agent run
        **base,
        **local,
    }

    # MCP configuration
    config["mcp"] = {
        "allow": [],
        "deny": [],
        "departments": {},
        **(base.get("mcp") or {}),
        **(local.get("mcp") or {}),
    }

    # Tool configuration
    config["tools"] = {
        "web": True,
        "browser": True,
        **(base.get("tools") or {}),
        **(local.get("tools") or {}),
    }

    # Team configuration
    config["teams"] = {
        "enabled": True,
        "max": 4,
        **(base.get("teams") or {}),
        **(local.get("teams") or {}),
    }

    # Environment overrides
    if os.getenv("AO_NAME"):
        config["name"] = os.getenv("AO_NAME")
    if os.getenv("AO_BRAIN"):
        config["brain"] = os.getenv("AO_BRAIN")
    if os.getenv("PORT"):
        config["port"] = int(os.getenv("PORT", "8000"))
    if os.getenv("AO_MODEL"):
        config["model"] = os.getenv("AO_MODEL")

    # Anthropic setup (local Claude or API key)
    if os.getenv("ANTHROPIC_AUTH_TOKEN"):
        config["anthropic_auth_token"] = os.getenv("ANTHROPIC_AUTH_TOKEN")
    if os.getenv("ANTHROPIC_BASE_URL"):
        config["anthropic_base_url"] = os.getenv("ANTHROPIC_BASE_URL")
    if os.getenv("ANTHROPIC_API_KEY"):
        config["anthropic_api_key"] = os.getenv("ANTHROPIC_API_KEY")

    # Model names (for local Claude)
    config["model_fable"] = os.getenv(
        "ANTHROPIC_DEFAULT_FABLE_MODEL", "cc/claude-fable-5"
    )
    config["model_opus"] = os.getenv("ANTHROPIC_DEFAULT_OPUS_MODEL", "cc/claude-opus-5")
    config["model_sonnet"] = os.getenv(
        "ANTHROPIC_DEFAULT_SONNET_MODEL", "cc/claude-sonnet-5"
    )
    config["model_haiku"] = os.getenv(
        "ANTHROPIC_DEFAULT_HAIKU_MODEL", "cc/claude-haiku-4-5-20251001"
    )

    # Resolve paths
    config["port"] = int(config.get("port", 8000)) or 8000
    config["brain_path"] = (ROOT / config["brain"]).resolve()

    return config


# Singleton
_config = None


def get_config() -> Dict[str, Any]:
    """Get cached config"""
    global _config
    if _config is None:
        _config = load_config()
    return _config
