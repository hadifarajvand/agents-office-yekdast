# Agent Office — Architecture Map & Master Plan

Status: draft for review · investigated and written 2026-09-19 by checking the running code directly (not assumptions).

This document answers three things the owner asked for:
1. **What is actually wired up right now** — a real map of the running stack, verified by reading the code, not the marketing copy.
2. **What "connected" currently means for each department and each integration** (Slack, Gmail, Google Calendar, Notion, Trello, brain) — and where the wiring quietly stops.
3. **A single step-by-step roadmap** to close the gap between "shows as connected in the UI" and "an agent can actually use it."

---

## 1. Current architecture (verified)

```
┌─────────────────────────────────────────────────────────────────────────┐
│  BROWSER (UI)                                                            │
│  dist/command-centre-v2.html — 3D office, chat, task feed                │
│  window.live / USE_PYTHON_BACKEND / SYNC_STRATEGY injected by serve.mjs  │
└───────────────┬───────────────────────────────────────┬─────────────────┘
                │ fetch /api/*                            │ EventSource /api/events
                ▼                                          ▼
┌─────────────────────────────────────────────────────────────────────────┐
│  FRONTEND SERVER — Node, serve.mjs, port 4520                            │
│  • Serves the built HTML, injects live-mode config                       │
│  • Owns: roster (office.agents.json), skills, routines, lessons, brain   │
│    NOTES (markdown vault under <brain>/Agents Office/), MCP connector    │
│    discovery + department binding (mcp.mjs)                              │
│  • Two execution paths live side by side:                                │
│     (a) LEGACY: runLive() spawns the `claude` CLI directly with          │
│         --allowedTools scoped to the department's connectors. THIS is    │
│         the only path that can actually call Gmail/Slack/Calendar/etc.   │
│     (b) CURRENT (USE_PYTHON_BACKEND=true): every GET/POST to             │
│         /api/tasks* is proxied straight to the Python backend instead.   │
│         The legacy path is dormant while this flag is on.                │
│  • Proxies /api/events (SSE) and /api/tasks* to the Python backend       │
└───────────────┬────────────────────────────────────────────────────────-┘
                │ HTTP proxy (proxyToPython)
                ▼
┌─────────────────────────────────────────────────────────────────────────┐
│  BACKEND — Python / FastAPI / LangGraph, port 8000                       │
│  backend/langgraph/graphs.py orchestrates one task through these nodes:  │
│                                                                            │
│   router_node → brain_context_node → lead_planning_node →                │
│   specialist_execution_node → synthesis_node → brain_update_node →       │
│   approval_node → complete_node                                          │
│                                                                            │
│  • brain_context_node DOES read the brain vault (load_brain() +          │
│    rank_by_relevance) — but it runs once per task, globally, for every   │
│    department. There is no per-lead / per-department scoping: every      │
│    task gets the same "top 5 relevant notes" ranking, lead or specialist.│
│  • Every agent has an `mcp_tools: [...]` list declared in                │
│    backend/langgraph/agents.py (e.g. ["web_search", "documents"]) —      │
│    this field is set but **never read by anything that calls a tool**.   │
│    specialist_execution_node calls the Claude API directly with no       │
│    tool definitions attached.                                            │
│  • Result: `used_tools` / `tools_used` in every node is either `[]` or   │
│    hardcoded to `["brain"]`. No task run through this backend has ever   │
│    called Gmail, Slack, Calendar, Notion, Trello, Xero, or anything else.│
└─────────────────────────────────────────────────────────────────────────┘
```

### The department → connector map (this part already exists and is correct)

`frontend/mcp.mjs` already hard-codes a sensible default department binding:

| Connector | Departments wired to it |
|---|---|
| Gmail | emails, sales, ops, fin, delivery |
| Slack | emails, ops, delivery |
| Google Calendar | emails, sales, delivery |
| Google Drive | ops, delivery, fin |
| Notion | all 6 departments |
| Trello / PandaDoc | ops, delivery |
| Xero / Stripe | fin |
| FullEnrich / Apollo / iMessage | sales |
| Meta / Clarity | marketing |

`office.config.json` can override this per-server via `"mcp": {"departments": {...}}`. This binding is real and correct — it is exactly what the top bar and `/api/health`'s `mcp.servers[].depts` reflect.

**The gap is not the binding. The gap is that nothing in the currently-active execution path (the Python backend) ever consults it or calls through it.** A connector showing "connected" in the top bar only means `claude mcp list` sees it on this machine — it says nothing about whether a running task can reach it, and today, none can.

### Brain: who actually talks to it

Today: **everyone, uniformly, centrally** — not "each lead talks to the brain" as a per-department relationship. `brain_context_node` runs once per task before the lead is even chosen, pulls the 5 most relevant notes office-wide, and hands them to whichever lead/specialists run next. There is no concept yet of "this department's own corner of the brain" vs. "everyone reads everything." That's a design decision to make explicitly in Phase 2 below, not a bug to silently fix.

### Branding

Naming is inconsistent across the codebase:
- `frontend/office.config.json` → `"name": "Northgate Studio"` (this is the *sample business name* the demo office is configured for — a customer name, not the product name)
- `frontend/src/shell.html` → `<title>Agents Office v3 (Beta)</title>`
- Root `package.json` → `"name": "agent-office-yekdast"`
- `frontend/package.json` → `"name": "agents-office"`
- Various comments/log lines → `"Agents Office"`

Product name should read **"Agent Office"** everywhere in the UI (title, chrome, log banners). The repository's own name is a separate, external, shared identifier (GitHub repo slug) — renaming that is a destructive, shared-visibility action (breaks clone URLs, CI, any bookmarks) and needs the owner's explicit go-ahead, done deliberately via `gh repo rename`, not folded into a UI copy pass. Flagging this rather than guessing: the repo is currently `agents-office-yekdast`; confirm the exact target spelling (`Yektas` vs `Yekdast`) before that rename happens.

---

## 2. Target architecture (proposed)

The direction (Python/LangGraph as the single execution engine, SSE for real-time UI) is right and should not be reversed. What's missing is the tool layer. Proposed shape:

```
Python backend (LangGraph)
   specialist_execution_node
        │
        ▼
   ToolBroker (new)  ──HTTP──▶  Node /api/mcp/invoke (new endpoint in serve.mjs)
        │                            │
        │                            ▼
        │                      mcp.mjs — same allow/deny/department
        │                      logic already used by the legacy path,
        │                      now serving both paths instead of one
        ▼
   used_tools / tools_used populated with what was actually called
```

Why route through Node instead of giving Python its own MCP client: the MCP servers here are the ones *this machine's Claude Code* is authenticated to (`claude mcp list` — Gmail, Slack, Calendar, Notion, Trello all show up because they're connected through the owner's Claude Code login, not a separate API key per service). Node already has that connection surface; duplicating OAuth/session handling in Python is unnecessary risk and drift. One broker, one place department/connector policy is enforced.

Brain: keep it centralized (office-wide relevance ranking) for now, but make it explicit in the UI and in this doc rather than implied — the roadmap below adds a Phase 2 decision point rather than assuming a change.

---

## 3. Master plan — step by step

**Phase 1 — Branding pass (small, safe, do first)**
1. `frontend/src/shell.html` `<title>` → `Agent Office`
2. Any hardcoded "Agents Office" UI copy in `src/` → `Agent Office`
3. Leave `office.config.json`'s `"name"` alone — that's the demo customer's business name, not the product name; confirm with owner if it should change too
4. Do **not** touch the GitHub repo slug in this pass — separate, owner-confirmed action

**Phase 2 — Decide brain scoping (decision, not code, first)**
5. Confirm with owner: should brain context stay office-wide-central (current behavior), or should each department/lead get its own scoped slice of the vault? Either is a real, defensible design — pick one deliberately.
6. Implement whichever is chosen in `brain_context_node` (scope `rank_by_relevance` by `state["department"]` if scoped is chosen).

**Phase 3 — Single source of truth for connector↔department binding**
7. Expose the existing `mcp.mjs` department map via a small read-only endpoint (`GET /api/mcp/bindings`) so Python never redeclares it.
8. Remove the redundant, unused `mcp_tools: [...]` literals from `backend/langgraph/agents.py`; derive each agent's available tools at runtime from its `department` + the bindings endpoint.

**Phase 4 — Build the tool broker**
9. Add `POST /api/mcp/invoke` to `serve.mjs`: takes `{server, tool, args, department}`, checks `allowed()`/`deptsFor()` from `mcp.mjs` (same policy the legacy CLI path already enforces), and only then proxies the call to Claude Code's MCP surface.
10. Add a thin Python client for that endpoint (`backend/services/mcp_broker.py`).

**Phase 5 — Wire it into the graph**
11. `specialist_execution_node` (and `lead_planning_node` where a lead needs to delegate a call) requests its allowed tool list from the broker, attaches real tool definitions to the Claude API call, and executes any tool_use the model returns through the broker.
12. Populate `used_tools`/`tools_used` from what was *actually* called, not a hardcoded list.

**Phase 6 — Verify per connector, one at a time**
13. Smoke-test each connector end-to-end through a real task: Gmail (emails dept), Slack (ops dept), Google Calendar (sales dept), Notion (any dept), Trello (ops/delivery). For each: confirm the specialist's `used_tools` shows the real call and the side effect actually happened (a Slack message sent, a calendar event created, etc.), exactly the way `check10s.js` was used this session to verify SSE — a live browser/API check, not a claim.
14. Record pass/fail per connector in this document's changelog section (add one below) before calling any of them "done."

**Phase 7 — Surface real status in the UI**
15. Change the top bar / department view so a connector shows three states, not two: *listed* (claude mcp list sees it), *bound* (a department can reach it per policy), *proven* (a real call succeeded in the last N days) — so "connected" in the UI stops being ambiguous.

---

## 4. Open questions for the owner (blocking Phase 2 and beyond)

- Brain scoping: office-wide (current) or per-department?
- Should a specialist call tools directly, or should every connector call be brokered through the department lead (mirrors the "lead owns the routine" pattern already used for Agent Teams)?
- Exact target spelling for the brand/repo rename (`Yektas` vs `Yekdast` vs current `agents-office-yekdast`) and whether the GitHub repo itself should be renamed or just the in-product name.
- Priority order for Phase 6 connectors — which one matters most first (Gmail and Slack look like the highest-value, lowest-risk starting points given they're already the most broadly department-bound).

---

## Changelog

- 2026-09-19 — Initial architecture audit and roadmap drafted. No code changed yet under this plan; this is the map to work from.
