"""Read-only GitHub access for agents (repo contents, issues, PRs, search).

Remote GitHub MCP server in read-only mode with a fine-grained token that has
Contents: read and Metadata: read on chosen repositories only. Even so, tools are
filtered here: a name that looks like a write is never handed to an agent.

UNVERIFIED until the runbook: the connection keys for the installed adapter version.
"""
from __future__ import annotations

import os
import re

from ..config import load_config
from .mcp_client import McpSession

WRITE_WORDS = re.compile(r"(create|update|delete|merge|push|add_|remove|fork|write|dispatch|run_|assign|close|reopen|"
                         r"lock|comment|review|approve|submit|rerun|cancel|label|transfer|archive)", re.IGNORECASE)


def is_read_tool(name: str) -> bool:
    return not WRITE_WORDS.search(name)


def session() -> McpSession:
    cfg = load_config().github
    token = os.environ.get(cfg["token_env"], "")
    if not token:
        raise RuntimeError(f'set {cfg["token_env"]} to a read-only fine-grained token to use GitHub')
    return McpSession("github", {"transport": "streamable_http", "url": cfg["url"],
                                 "headers": {"Authorization": f"Bearer {token}", "X-MCP-Readonly": "true"}})


async def read_tools(sess: McpSession | None = None) -> list:
    sess = sess or session()
    return [t for name, t in (await sess.tools()).items() if is_read_tool(name)]
