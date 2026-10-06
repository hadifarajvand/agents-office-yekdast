#!/usr/bin/env python3
"""Expand _registry.yaml into individual agent .md definition files.

For each entry in .claude/agents/_registry.yaml, generates a runnable agent
definition at .claude/agents/<domain>/<id>.md with YAML frontmatter and a
templated system prompt. Skips if the file already exists (preserves hand-written agents).
"""

from __future__ import annotations

import sys
from pathlib import Path

import yaml

REPO_ROOT = Path(__file__).resolve().parents[1]
REGISTRY_PATH = REPO_ROOT / ".claude" / "agents" / "_registry.yaml"
AGENTS_DIR = REPO_ROOT / ".claude" / "agents"

# Default tier per domain
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


def load_registry() -> list[dict]:
    with open(REGISTRY_PATH) as f:
        data = yaml.safe_load(f)
    return data.get("agents", [])


def agent_file_exists(agent: dict) -> bool:
    """Check if this agent already has a hand-written .md file (flat or in domain subdir)."""
    domain = agent["domain"]
    agent_id = agent["id"]

    # Check domain subdir
    domain_path = AGENTS_DIR / domain / f"{agent_id}.md"
    if domain_path.exists():
        return True

    # Check flat (the 11 hand-written ones)
    flat_path = AGENTS_DIR / f"{agent_id}.md"
    if flat_path.exists():
        return True

    return False


def generate_agent_md(agent: dict) -> str:
    """Generate a runnable agent .md definition."""
    agent_id = agent["id"]
    name = agent["name"]
    domain = agent["domain"]
    description = agent.get("description", "")
    tier = agent.get("tier", DOMAIN_TIER_DEFAULTS.get(domain, "reasoning_fast"))
    tools = agent.get("tools", [])
    skills = agent.get("skills", [])

    tools_line = f"tools: {tools}" if tools else "tools: []"
    skills_line = f"skills: {skills}" if skills else "skills: []"

    domain_title = domain.replace("_", " ").title()

    return f"""---
name: {name}
id: {agent_id}
domain: {domain}
tier: {tier}
rag_enabled: true
{tools_line}
{skills_line}
---

# {name}

You are the **{name}** agent in the Citadel SaaS Factory fleet.

## Role

{description}

## Domain

{domain_title}

## Operating Parameters

- **Tier**: {tier} (routed via models/routing.yaml)
- **RAG**: Enabled (agentic retrieval via backbone/rag/)
- **Guardrails**: All outputs pass through the triple-layer validation pipeline
- **Audit**: Every action is logged to the immutable audit trail

## RAG Retrieval Prompt

When answering questions within your domain, use the following retrieval strategy:

**System**: You are {name}, a specialized {domain_title} agent. Your knowledge is grounded
in the project's documentation, codebase, and domain-specific references stored in the
RAG vector store.

**Retrieval instructions**:
1. Decompose the user query into retrieval-optimized sub-queries relevant to {domain_title}.
2. Retrieve chunks from the vector store using domain-scoped metadata filters:
   `{{"domain": "{domain}", "agent_id": "{agent_id}"}}`.
3. Grade each retrieved chunk for relevance (threshold: 0.5). Discard irrelevant chunks.
4. If fewer than 2 relevant chunks remain, rewrite the query with domain-specific terminology
   and retry (max 3 iterations).
5. Generate your response using ONLY the retrieved context. Cite sources inline as [chunk-id].
6. Self-check: verify every factual claim maps to a retrieved span. Remove ungrounded claims.

**Domain keywords for retrieval**: {description}

## LLM System Prompt

You are {name}, part of the Citadel SaaS Factory agent fleet (265 agents, 15 domains).

Your domain is {domain_title}. Your expertise: {description}.

Rules:
1. Stay within your domain. Defer out-of-scope requests to the appropriate domain agent.
2. Ground all factual claims in retrieved context. Use [chunk-id] citations.
3. Follow project conventions (see .claude/rules/).
4. Report confidence: high (grounded in sources), medium (inferred), low (speculative).
5. Escalate security concerns to security domain agents immediately.
6. Never fabricate data, metrics, or code examples. If uncertain, say so.
"""


def main() -> int:
    agents = load_registry()
    created = 0
    skipped = 0

    for agent in agents:
        if agent_file_exists(agent):
            skipped += 1
            continue

        domain = agent["domain"]
        agent_id = agent["id"]
        domain_dir = AGENTS_DIR / domain
        domain_dir.mkdir(parents=True, exist_ok=True)

        md_content = generate_agent_md(agent)
        output_path = domain_dir / f"{agent_id}.md"
        output_path.write_text(md_content, encoding="utf-8")
        created += 1

    total = created + skipped
    print(f"Registry expansion complete: {total} agents total, {created} created, {skipped} skipped (pre-existing)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
