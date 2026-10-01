"""Model calls via the owner's local router/proxy (langchain-anthropic's ChatAnthropic
pointed at ANTHROPIC_BASE_URL / ANTHROPIC_AUTH_TOKEN), replacing serve.mjs's askX().

The proxy runs on the owner's laptop at 127.0.0.1:20128, reachable from inside the app
container as host.docker.internal:20128 (wired via extra_hosts in docker-compose.yml).
"""
from __future__ import annotations

import json
import os
import re

from langchain_anthropic import ChatAnthropic

from .mcp import registry as mcp_registry
from .models import HAIKU_MODEL_ID, model_id

BASE_URL = os.environ.get("ANTHROPIC_BASE_URL", "http://host.docker.internal:20128/v1")
AUTH_TOKEN = os.environ.get("ANTHROPIC_AUTH_TOKEN", "")


def _client(model: str, max_tokens: int = 4096) -> ChatAnthropic:
    return ChatAnthropic(
        model=model,
        anthropic_api_url=BASE_URL,
        anthropic_api_key=AUTH_TOKEN or "none",
        max_tokens=max_tokens,
        timeout=120,
    )


async def ask(system: str, user: str, *, model_key: str | None = None, max_tokens: int = 4096) -> str:
    """Plain text completion — mirrors serve.mjs's ask()."""
    mid = model_id(model_key) if model_key else model_id("sonnet")
    llm = _client(mid, max_tokens)
    resp = await llm.ainvoke([("system", system), ("human", user)])
    return resp.content if isinstance(resp.content, str) else str(resp.content)


async def ask_haiku_json(system: str, user: str) -> dict:
    """The router hop — always Haiku, never part of the agent model precedence chain."""
    llm = _client(HAIKU_MODEL_ID, max_tokens=512)
    resp = await llm.ainvoke([("system", system), ("human", user)])
    text = resp.content if isinstance(resp.content, str) else str(resp.content)
    return parse_json(text)


def parse_json(text: str) -> dict:
    t = re.sub(r"^```(json)?|```$", "", text.strip(), flags=re.MULTILINE).strip()
    m = re.search(r"\{.*\}", t, re.DOTALL)
    if not m:
        raise ValueError(f"no JSON object found in: {text[:200]}")
    return json.loads(m.group(0))
