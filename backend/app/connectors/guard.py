"""Allow-list and audit guard around any tool-calling client (MCP or otherwise)."""
from __future__ import annotations

import logging
import re
from pathlib import Path
from typing import Any, Awaitable, Callable

from .. import db, policy
from ..config import load_config

log = logging.getLogger("agents_office.connectors")

# Never callable through a connector, even if someone lists them in the allow-list:
# anything that deletes, administers, or reaches other systems.
HARD_DENY = re.compile(r"(remove|delete|destroy|prune|purge|drop|user|settings|server|ssh|backup|restore|certificate|"
                       r"registry|notification|admin|reboot|shutdown|migrate|wipe)", re.IGNORECASE)


class Refused(PermissionError):
    pass


class AllowListError(ValueError):
    pass


def validate_allowlist(names: list[str]) -> None:
    bad = [n for n in names if HARD_DENY.search(n)]
    if bad:
        raise AllowListError(f"the allow-list contains destructive or administrative tools: {', '.join(bad)}")


class Guard:
    """call(tool, args): refuses anything not allow-listed, audits first, redacts the result."""

    def __init__(self, server: str, allow: list[str], invoke: Callable[[str, dict], Awaitable[Any]], *,
                 agent: str = "orchestrator", dept: str = "devops"):
        validate_allowlist(allow)
        self.server, self.allow, self._invoke, self.agent, self.dept = server, set(allow), invoke, agent, dept

    async def call(self, tool: str, args: dict | None = None) -> Any:
        args = args or {}
        resource = str({k: v for k, v in args.items() if k not in ("password", "token", "apiKey", "key")})[:300]
        allowed = tool in self.allow and not HARD_DENY.search(tool)
        reason = "" if allowed else "not on the allow-list"
        # Audit BEFORE the call, in both the log file and the database.
        try:
            policy.append_audit_log(Path(load_config().brain_path),
                                    policy.audit_log_line(self.agent, self.dept, self.server, tool, resource, allowed, reason))
            await db.audit(self.agent, self.dept, self.server, tool, policy.redact(resource), allowed, reason)
        except Exception:
            log.exception("could not write the audit record; refusing the call")
            raise Refused("audit unavailable")
        if not allowed:
            raise Refused(policy.refusal(f"{self.server} tool {tool} is not allowed", "the owner"))
        return await self._invoke(tool, args)
