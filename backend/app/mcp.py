"""Port of mcp.mjs — connectors (Path B policy layer), STUBBED for Docker per the owner's choice.

The Node original shells out to `claude mcp list` to discover servers your local Claude Code
is connected to. That doesn't exist inside a container. This port keeps every piece of PURE
POLICY logic 1:1 (allow/deny/department wiring, the prompt text, the refusal rules) because
that is the pre-tool-call policy hook (Path B) the graph's tool-call node must enforce —
but `discover()` is stubbed to return an empty list rather than spawning a subprocess.

Real connectivity returns via `langchain-mcp-adapters`, configured with explicit server
URLs/tokens (not CLI discovery) — tracked as follow-up work, not part of this stub.
"""
from __future__ import annotations

import re

from . import policy

DEPT_KEYS = ["exec", "revenue", "engineering", "frontend", "devops", "secdata", "fin", "content"]

ALIASES = {
    "gmail": ["gmail", "googlegmail"], "notion": ["notion"], "canva": ["canva"],
    "meta": ["metaads", "meta", "facebookads", "facebook"], "slack": ["slack"],
    "fullenrich": ["fullenrich"], "apollo": ["apollo", "apolloio"], "xero": ["xero"], "stripe": ["stripe"],
    "pandadoc": ["pandadoc"], "clarity": ["clarity", "microsoftclarity"], "beehiiv": ["beehiiv"], "loops": ["loops"],
    "hyperframes": ["hyperframes"], "imessage": ["imessage", "messages"], "claude": ["claude"], "chatgpt": ["chatgpt", "openai"],
    "googlecalendar": ["googlecalendar", "gcal", "calendar"], "googledrive": ["googledrive", "gdrive", "drive"],
    "webflow": ["webflow"], "playwright": ["playwright"], "higgsfield": ["higgsfield", "higgfield"], "territool": ["territool"],
}

DEPTS_BY_KEY = {
    "meta": ["revenue"], "canva": ["revenue", "content"], "loops": ["revenue"], "beehiiv": ["revenue"],
    "hyperframes": ["revenue"], "clarity": ["revenue"], "notion": DEPT_KEYS,
    "gmail": ["content", "revenue", "devops", "fin", "engineering"], "fullenrich": ["revenue"], "imessage": ["revenue"],
    "apollo": ["revenue"], "pandadoc": ["devops", "engineering"], "xero": ["fin"], "stripe": ["fin"],
    "slack": ["content", "devops", "engineering"], "googledrive": ["devops", "engineering", "fin"],
    "googlecalendar": ["content", "revenue", "engineering"], "playwright": ["engineering", "devops"],
    "github": ["engineering", "devops"], "linear": ["engineering", "devops"], "jira": ["engineering", "devops"],
    "hubspot": ["revenue"], "salesforce": ["revenue"], "zapier": DEPT_KEYS,
    "figma": ["revenue", "frontend"], "webflow": ["revenue", "frontend"], "higgsfield": ["revenue"],
    "territool": ["revenue"],
}


def norm(s: str) -> str:
    s = re.sub(r"^claude\.ai\s+", "", str(s).lower())
    s = re.sub(r"\s+mcp$", "", s)
    return re.sub(r"[^a-z0-9]", "", s)


def tool_id(name: str) -> str:
    return re.sub(r"[^A-Za-z0-9_]+", "_", str(name))


def _display(name: str) -> str:
    s = re.sub(r"^claude\.ai\s+", "", str(name))
    return re.sub(r"\s+MCP$", "", s)


def _logo_key(name: str) -> str | None:
    n = norm(name)
    for key, aliases in ALIASES.items():
        if n in aliases:
            return key
    return None


STATUS = {"✔": "connected", "✓": "connected", "!": "needs-auth", "✗": "failed", "✘": "failed", "⏸": "pending"}


class MCPRegistry:
    def __init__(self):
        self.servers: list[dict] = []
        self.discovered_at: float = 0
        self.cfg_mcp = {"allow": [], "deny": [], "departments": {}}
        self.cfg_web = True
        self.web_bound = False  # set True only when a real web search/fetch tool is wired
        self.bound_tools: dict[str, list] = {}   # server key -> LangChain tools actually connected
        self._tool_server: dict[str, str] = {}   # tool name -> server key

    def configure(self, cfg: dict, valid_depts: set[str] | None = None) -> None:
        self.cfg_mcp = {"allow": [], "deny": [], "departments": {}, **(cfg.get("mcp") or {})}
        self.cfg_web = cfg.get("tools", {}).get("web") is not False
        if valid_depts is not None:
            self._assert_depts_known(valid_depts)

    def _assert_depts_known(self, valid_depts: set[str]) -> None:
        """Fail loud if a connector's department wiring names a department that
        doesn't exist in the live roster, instead of silently dropping it at
        request time (see `_depts_for`)."""
        bad = {d for v in DEPTS_BY_KEY.values() for d in v if d not in valid_depts}
        for v in (self.cfg_mcp.get("departments") or {}).values():
            bad |= {d for d in v if d not in valid_depts}
        if bad:
            raise ValueError(
                f"mcp department wiring references unknown department(s) {sorted(bad)}; "
                f"known departments are {sorted(valid_depts)}"
            )

    def _matches(self, s: dict, x: str) -> bool:
        n = norm(x)
        return bool(n) and (norm(s["name"]) == n or s["id"] == x or s.get("key") == n or tool_id(x) == s["id"])

    def _denied(self, s: dict) -> bool:
        return any(self._matches(s, x) for x in self.cfg_mcp["deny"])

    def _allowed(self, s: dict) -> bool:
        if self._denied(s):
            return False
        allow = self.cfg_mcp["allow"]
        return not allow or any(self._matches(s, x) for x in allow)

    def _depts_for(self, name: str, key: str | None) -> list[str]:
        for k, v in (self.cfg_mcp.get("departments") or {}).items():
            if norm(k) == norm(name) or (key and norm(k) == key):
                return [d for d in v if d in DEPT_KEYS]
        return DEPTS_BY_KEY.get(key or norm(name), DEPT_KEYS)

    def _make(self, name: str, target: str, status: str) -> dict:
        key = _logo_key(name)
        return {
            "id": tool_id(name), "name": _display(name), "key": key, "status": status,
            "target": target or "", "source": "claude.ai" if re.match(r"^claude\.ai\s", name, re.IGNORECASE) else "local",
            "depts": self._depts_for(name, key), "tools": [],
        }

    def parse_list(self, text: str) -> list[dict]:
        out = []
        for raw in str(text).split("\n"):
            line = re.sub(r"\x1b\[[0-9;]*m", "", raw).strip()
            m = re.match(r"^(.+?):\s+(.+?)\s+-\s+(\S)\s*(.*)$", line)
            if not m:
                continue
            status = STATUS.get(m.group(3)) or ("connected" if re.search("connected", m.group(4), re.IGNORECASE)
                                                 else "needs-auth" if re.search("auth", m.group(4), re.IGNORECASE) else "failed")
            out.append(self._make(m.group(1), m.group(2), status))
        return out

    async def discover(self, timeout: float = 45.0) -> list[dict]:
        """Stubbed for Docker: no `claude mcp list` subprocess inside the container.
        Returns the servers from the last `from_init` observation, if any; empty otherwise."""
        return self.servers

    def from_init(self, init: dict | None) -> None:
        if not init or not isinstance(init.get("mcp_servers"), list):
            return
        tools = init.get("tools") if isinstance(init.get("tools"), list) else []
        for m in init["mcp_servers"]:
            sid = tool_id(m["name"])
            s = next((x for x in self.servers if x["id"] == sid), None)
            if not s:
                s = self._make(m["name"], "", "connected")
                self.servers.append(s)
            if m.get("status") in ("connected", "needs-auth", "failed"):
                s["status"] = m["status"]
            elif m.get("status") == "pending" and s["status"] != "connected":
                s["status"] = "pending"
            mine = [t[len(s["id"]) + 7:] for t in tools if t.startswith(f'mcp__{s["id"]}__')]
            if mine:
                s["tools"] = mine
                s["status"] = "connected"
        import time
        self.discovered_at = self.discovered_at or time.time()

    def list(self) -> list[dict]:
        return self.servers

    def usable(self) -> list[dict]:
        return [s for s in self.servers if s["status"] == "connected" and self._allowed(s)]

    def call_allowed(self, dept: str, key: str) -> tuple[bool, str | None]:
        """Call-time policy gate (Task 2): checked fresh on every tool-call event
        during the specialist loop, never cached from a decision made earlier in
        the loop or from what's merely named in the prompt (mcp.py's existing
        prompt_text() filtering stays as defense-in-depth, not the enforcement
        point). Returns (allowed, refusal_message)."""
        s = next((x for x in self.servers if x.get("key") == key or x["id"] == key), None)
        if not s or not self._allowed(s):
            return False, policy.refusal(f"{key} not wired to {dept} department", "the owner")
        if dept not in self._depts_for(s["name"], s.get("key")):
            return False, policy.refusal(f"{s['name']} not wired to {dept} department", "the owner")
        return True, None

    def attach_tools(self, server_key: str, tools: list, name: str | None = None) -> None:
        """Register real tools for a connector (e.g. GitHub read-only) and mark it connected."""
        self.bound_tools[server_key] = list(tools)
        for t in tools:
            self._tool_server[t.name] = server_key
        sid = tool_id(name or server_key)
        if not any(x["id"] == sid for x in self.servers):
            self.servers.append(self._make(name or server_key, "", "connected"))
        for x in self.servers:
            if x["id"] == sid:
                x["status"] = "connected"
                x["tools"] = [t.name for t in tools]

    def server_of_tool(self, tool_name: str) -> str | None:
        return self._tool_server.get(tool_name)

    def tools_for(self, agent_tools: list[str]) -> list:
        """Tools this agent may be handed: only those of connectors it names in its
        `tools` list. The call-time gate (call_allowed) still checks every single call."""
        wanted = {norm(t) for t in (agent_tools or [])}
        out = []
        for key, tools in self.bound_tools.items():
            if norm(key) in wanted:
                out.extend(tools)
        return out

    def allowed_tools(self) -> list[str]:
        t = [f'mcp__{s["id"]}' for s in self.usable()]
        if self.cfg_web and self.web_bound:
            t += ["WebSearch", "WebFetch"]
        return t

    def key_of(self, tool_name: str) -> str | None:
        m = re.match(r"^mcp__(.+?)__", tool_name)
        if not m:
            return None
        s = next((x for x in self.servers if x["id"] == m.group(1)), None)
        return (s.get("key") or s["id"]) if s else m.group(1)

    def names_of(self, tool_names: list[str]) -> list[str]:
        out = []
        for n in tool_names:
            m = re.match(r"^mcp__(.+?)__", n)
            if m:
                s = next((x for x in self.servers if x["id"] == m.group(1)), None)
                v = s["name"] if s else m.group(1)
            else:
                v = "web search" if n == "WebSearch" else "web fetch" if n == "WebFetch" else None
            if v:
                out.append(v)
        seen = set()
        return [x for x in out if not (x in seen or seen.add(x))]

    def summary(self) -> dict:
        return {
            "discoveredAt": self.discovered_at, "web": self.cfg_web and self.web_bound,
            "servers": [{**s, "allowed": self._allowed(s), "denied": self._denied(s)} for s in self.servers],
        }

    def prompt_text(self, agent_tools: list[str] | None = None) -> str:
        """What the agent is told about its tools. Only tools that are actually bound
        are named: the office never claims web search or a connector it does not have."""
        agent_tools = agent_tools or []
        u = self.usable()
        web = self.cfg_web and self.web_bound
        if not u:
            return ("TOOLS\nWeb search and web fetch. No business connectors are connected."
                    if web else "TOOLS\nNone connected. Work from the brief and the notes you are given.")
        lines = [
            f'- {s["name"]} (mcp__{s["id"]}__*)' + (': ' + ', '.join(s["tools"][:12]) + ('…' if len(s["tools"]) > 12 else '') if s["tools"] else '')
            for s in u
        ]
        mine = [s for s in u if any(k == s.get("key") or norm(k) == norm(s["name"]) for k in agent_tools)]
        text = "TOOLS\nYou can call these connectors:\n" + "\n".join(lines)
        if web:
            text += "\n- Web search and web fetch"
        if mine:
            text += f'\nYour usual tools: {", ".join(s["name"] for s in mine)}.'
        text += ('\nRules: read freely (search, list, fetch) when it makes the work better. Anything that sends, '
                  "posts, pays, deletes or changes data outside this machine — do it ONLY when the owner's request "
                  "explicitly asks for that exact action; otherwise prepare it and say what you would send. Never "
                  "ask the owner a question mid-task; make a reasonable assumption and mark it (assumed).")
        return text


registry = MCPRegistry()
