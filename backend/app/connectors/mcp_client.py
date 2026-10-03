"""Real MCP access through langchain-mcp-adapters. Used by the Dokploy and GitHub
connectors; tests replace `invoke` with a fake, so nothing here runs offline.

UNVERIFIED until the laptop runbook: the exact connection dict keys for the installed
adapter version (0.3.x) and the tool names each server exposes."""
from __future__ import annotations

from typing import Any


class McpSession:
    def __init__(self, name: str, connection: dict):
        self.name, self.connection = name, connection
        self._tools: dict[str, Any] | None = None

    async def tools(self) -> dict[str, Any]:
        if self._tools is None:
            from langchain_mcp_adapters.client import MultiServerMCPClient
            client = MultiServerMCPClient({self.name: self.connection})
            self._tools = {t.name: t for t in await client.get_tools()}
        return self._tools

    async def invoke(self, tool: str, args: dict) -> Any:
        tools = await self.tools()
        if tool not in tools:
            raise KeyError(f"{self.name} does not expose a tool called {tool}; it has {sorted(tools)[:20]}")
        return await tools[tool].ainvoke(args)
