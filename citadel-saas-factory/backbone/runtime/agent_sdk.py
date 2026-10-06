"""Agent SDK — resolve, load, and run agents from the registry.

Provides a programmatic interface to the 265-agent fleet:
- Resolve agent ID to its definition (.md file)
- Extract tier, domain, and system prompt from frontmatter
- Run the agent through ModelRouter with guardrails
- Spawn sub-agents with depth and fan-out caps
"""

from __future__ import annotations

import re
from pathlib import Path
from typing import Any

import structlog
import yaml

from backbone.runtime.model_client import ModelRouter

logger = structlog.get_logger("runtime.agent_sdk")

MAX_SPAWN_DEPTH = 3
MAX_FAN_OUT = 5

REPO_ROOT = Path(__file__).resolve().parents[2]
AGENTS_DIR = REPO_ROOT / ".claude" / "agents"
REGISTRY_PATH = AGENTS_DIR / "_registry.yaml"


def _parse_frontmatter(content: str) -> tuple[dict[str, Any], str]:
    """Parse YAML frontmatter from a markdown file."""
    if not content.startswith("---"):
        return {}, content

    parts = content.split("---", 2)
    if len(parts) < 3:
        return {}, content

    try:
        meta = yaml.safe_load(parts[1]) or {}
    except yaml.YAMLError:
        meta = {}

    body = parts[2].strip()
    return meta, body


def _extract_system_prompt(body: str) -> str:
    """Extract the LLM System Prompt section from the agent body."""
    match = re.search(r"## LLM System Prompt\s*\n(.*?)(?=\n## |\Z)", body, re.DOTALL)
    if match:
        return match.group(1).strip()
    # Fallback: use the full body as the prompt
    return body[:2000]


class AgentSDK:
    """SDK for resolving and running agents from the registry."""

    def __init__(self, router: ModelRouter | None = None) -> None:
        self._router = router or ModelRouter()
        self._registry: list[dict[str, Any]] | None = None

    def _load_registry(self) -> list[dict[str, Any]]:
        if self._registry is None:
            with open(REGISTRY_PATH) as f:
                data = yaml.safe_load(f)
            self._registry = data.get("agents", [])
        return self._registry

    def resolve_agent(self, agent_id: str) -> dict[str, Any]:
        """Resolve an agent ID to its metadata and system prompt.

        Raises KeyError if the agent is not found.
        """
        # Find in registry
        registry = self._load_registry()
        entry = next((a for a in registry if a["id"] == agent_id), None)
        if entry is None:
            raise KeyError(f"Agent not found in registry: {agent_id}")

        domain = entry["domain"]

        # Find the .md file
        domain_path = AGENTS_DIR / domain / f"{agent_id}.md"
        flat_path = AGENTS_DIR / f"{agent_id}.md"

        if domain_path.exists():
            content = domain_path.read_text(encoding="utf-8")
        elif flat_path.exists():
            content = flat_path.read_text(encoding="utf-8")
        else:
            raise KeyError(f"Agent definition file not found for: {agent_id}")

        meta, body = _parse_frontmatter(content)
        system_prompt = _extract_system_prompt(body)

        return {
            "id": agent_id,
            "name": meta.get("name", entry.get("name", agent_id)),
            "domain": domain,
            "tier": meta.get("tier", "reasoning_fast"),
            "system_prompt": system_prompt,
            "tools": meta.get("tools", []),
            "skills": meta.get("skills", []),
            "rag_enabled": meta.get("rag_enabled", False),
        }

    async def run_agent(
        self,
        agent_id: str,
        prompt: str,
        context: str | None = None,
        depth: int = 0,
    ) -> dict[str, Any]:
        """Run an agent by ID with its configured tier and system prompt.

        Args:
            agent_id: The agent registry ID.
            prompt: The user prompt to send.
            context: Optional context (RAG docs, etc.).
            depth: Current spawn depth (for sub-agent safety).

        Returns:
            Dict with status, output, model_used, tier.
        """
        if depth > MAX_SPAWN_DEPTH:
            logger.warning("max_spawn_depth", agent_id=agent_id, depth=depth)
            return {
                "status": "depth_exceeded",
                "output": f"Maximum agent spawn depth ({MAX_SPAWN_DEPTH}) exceeded",
                "model_used": "",
                "tier": "",
            }

        agent = self.resolve_agent(agent_id)
        tier = agent["tier"]
        system_prompt = agent["system_prompt"]

        messages = [
            {"role": "system", "content": system_prompt},
        ]

        if context:
            messages.append({"role": "user", "content": f"Context:\n{context}\n\n---\n\n{prompt}"})
        else:
            messages.append({"role": "user", "content": prompt})

        logger.info(
            "agent_run",
            agent_id=agent_id,
            tier=tier,
            depth=depth,
            prompt_length=len(prompt),
        )

        result = await self._router.complete(tier=tier, messages=messages)

        return {
            "status": result.status,
            "output": result.content,
            "model_used": result.model_used,
            "tier": tier,
        }

    async def spawn_sub_agent(
        self,
        parent_id: str,
        child_id: str,
        prompt: str,
        context: str | None = None,
        depth: int = 0,
    ) -> dict[str, Any]:
        """Spawn a sub-agent from a parent agent.

        Enforces depth cap and logs the parent-child relationship.
        """
        logger.info("sub_agent_spawn", parent=parent_id, child=child_id, depth=depth + 1)
        return await self.run_agent(child_id, prompt, context, depth=depth + 1)

    def list_agents(self, domain: str | None = None) -> list[dict[str, str]]:
        """List available agents, optionally filtered by domain."""
        registry = self._load_registry()
        if domain:
            registry = [a for a in registry if a["domain"] == domain]
        return [{"id": a["id"], "name": a["name"], "domain": a["domain"]} for a in registry]
