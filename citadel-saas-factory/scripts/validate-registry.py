#!/usr/bin/env python3
"""Validate that every registry entry has a matching .md definition and resolvable tier."""

from __future__ import annotations

import sys
from pathlib import Path

import yaml

REPO_ROOT = Path(__file__).resolve().parents[1]
REGISTRY_PATH = REPO_ROOT / ".claude" / "agents" / "_registry.yaml"
AGENTS_DIR = REPO_ROOT / ".claude" / "agents"
ROUTING_PATH = REPO_ROOT / "models" / "routing.yaml"

DOMAIN_TIER_DEFAULTS: dict[str, str] = {
    "executive": "reasoning_deep",
    "marketing": "cheap_fast",
    "sales": "reasoning_fast",
    "customer_success": "reasoning_fast",
    "product": "reasoning_fast",
    "engineering": "reasoning_fast",
    "frontend": "reasoning_fast",
    "devops": "reasoning_fast",
    "security": "reasoning_deep",
    "data": "reasoning_fast",
    "qa": "reasoning_fast",
    "hr": "cheap_fast",
    "finance": "reasoning_fast",
    "legal": "reasoning_deep",
    "content": "cheap_fast",
}


def main() -> int:
    # Load registry
    with open(REGISTRY_PATH) as f:
        registry = yaml.safe_load(f)
    agents = registry.get("agents", [])

    # Load routing tiers
    with open(ROUTING_PATH) as f:
        routing = yaml.safe_load(f)
    available_tiers = set(routing.get("tiers", {}).keys())

    errors: list[str] = []
    total = 0

    for agent in agents:
        total += 1
        agent_id = agent["id"]
        domain = agent["domain"]
        tier = agent.get("tier", DOMAIN_TIER_DEFAULTS.get(domain, "reasoning_fast"))

        # Check .md file exists (either in domain subdir or flat)
        domain_path = AGENTS_DIR / domain / f"{agent_id}.md"
        flat_path = AGENTS_DIR / f"{agent_id}.md"

        if not domain_path.exists() and not flat_path.exists():
            errors.append(f"MISSING .md: {agent_id} (domain={domain})")

        # Check tier resolves
        if tier not in available_tiers:
            errors.append(f"UNRESOLVABLE TIER: {agent_id} tier={tier}")

    if errors:
        print(f"VALIDATION FAILED: {len(errors)} errors in {total} agents")
        for err in errors[:20]:
            print(f"  - {err}")
        if len(errors) > 20:
            print(f"  ... and {len(errors) - 20} more")
        return 1

    print(f"VALIDATION PASSED: {total} executable agents, all tiers resolvable")
    return 0


if __name__ == "__main__":
    sys.exit(main())
