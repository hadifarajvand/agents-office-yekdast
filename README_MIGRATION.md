# Quick Start: Agents Office + LangGraph

You now have a complete blueprint for migrating agents-office to LangGraph. Here's what you have:

## Documents Created

1. **LANGGRAPH_MIGRATION.md** (14KB)
   - Full architectural overview
   - Why LangGraph vs direct Claude
   - State graphs, node functions, edge routing
   - Team execution & routine orchestration
   - MCP integration strategy
   - Phased migration timeline
   - **Start here** for understanding the big picture

2. **IMPLEMENTATION_GUIDE.md** (12KB)
   - Ready-to-use Python code templates
   - Project structure & directory layout
   - Core nodes (load_context, route_agent, run_agent, save_deliverable)
   - FastAPI server setup
   - MCP tool manager
   - Subprocess sandboxing
   - Unit tests
   - **Start here** to write code

3. **SANDBOXING_GUIDE.md** (10KB)
   - Three sandboxing approaches (subprocess, container, Kubernetes)
   - Permission model & tool whitelisting
   - Audit logging & security checklist
   - Testing examples
   - Decision matrix
   - **Read this** before choosing a sandbox strategy

---

## Key Takeaways

### Why LangGraph?

| Current agents-office | LangGraph |
|--------|-----------|
| Implicit routing (prompt-driven) | Explicit state graph |
| Polling for approvals | Conditional edges + checkpoints |
| Sequential team runs (spawn processes) | Parallel graph nodes |
| Custom routine clock | First-class RoutineState graph |
| Ad-hoc tool execution | Centralized executor with auditing |

### Architecture Overview

```
User Input (task bar)
  ↓
StateGraph("load_context" → "route" → "run_agent" → "save")
  ↓
Each node = async function
  ↓
State checkpoint after each node
  ↓
Deliverable saved + Brain rebuilt
```

### Three Sandboxing Options

1. **Subprocess** (dev/demo)
   - Subprocess isolation, no containers
   - 5-50ms overhead
   - Good for development

2. **Docker** (production)
   - Container with memory/CPU limits
   - 500ms-2s overhead
   - Recommended for most cases

3. **Kubernetes** (scale)
   - Native K8s integration
   - Multi-machine deployment
   - For compliance-heavy orgs

---

## Implementation Path

### Phase 1: Single-Agent (Week 1)
```python
# Start here
from langgraph.graphs import build_office_graph

graph = build_office_graph()
final_state = graph.invoke({
    'task_id': 'task-1',
    'task_text': 'Write a blog post',
    'department': 'marketing'
})
```

### Phase 2: Add Tools (Week 2-3)
```python
# Integrate MCP servers via tool_manager
tools = await tool_manager.get_tools_for_agent('alice', 'marketing')

# Execute with Claude + tools
response = await run_agent_with_tools(state, tools)
```

### Phase 3: Sandboxing (Week 3-4)
```python
# Wrap tool execution
executor = SubprocessToolExecutor()
result = await executor.execute(tool_call, agent_id, task_id)
```

### Phase 4: Teams & Routines (Week 4-5)
```python
# Teams: lead splits → teammates run in parallel
# Routines: separate RoutineState graph, scheduled by server clock
```

### Phase 5: Production Ready (Week 6+)
```python
# Checkpointer: PostgreSQL persistence
# MCP: langchain-mcp-adapters integration
# Monitoring: Prometheus metrics on latency, tool success rates
```

---

## Core Technologies

- **LangGraph**: State management + graph orchestration (Python)
- **Anthropic SDK**: Claude API calls with tool use
- **FastAPI**: HTTP API (replace serve.mjs)
- **langchain-mcp-adapters**: MCP server discovery + tool loading
- **Docker** (optional): Container sandbox
- **PostgreSQL** (optional): State checkpointing

---

## API Compatibility

You keep the same `/api/*` endpoints — no frontend changes needed:

```
POST /api/tasks                 # Create task
GET  /api/tasks/:id             # Get status
POST /api/tasks/:id/approve     # Approve pending task
POST /api/tasks/:id/messages    # Chat with agent
GET  /api/skills                # List skills
```

Backend swaps from Node.js (serve.mjs) to Python (FastAPI).

---

## Decision: For Your Demo

**Recommendation:**
1. Use **Subprocess** sandbox (Week 3-4)
   - No Docker overhead
   - Easy to demo locally
   - Full isolation for read-only tools

2. **Optional:** Layer Docker on top later
   - Once you need to scale or show it to customers
   - Production customers will expect container isolation

3. **Keep:**
   - office.agents.json (agent roster)
   - office.config.json (tool permissions)
   - <brain>/Agents Office/skills/ (skill workflows)
   - <brain>/Agents Office/feedback/ (learned rules)
   - <brain>/ (your notes)

---

## File Structure

```
your-agents-office/
├── LANGGRAPH_MIGRATION.md       ← Architecture guide
├── IMPLEMENTATION_GUIDE.md      ← Code templates
├── SANDBOXING_GUIDE.md          ← Security strategies
├── README_MIGRATION.md          ← This file
│
├── office.config.json           ← Kept as-is
├── office.agents.json           ← Kept as-is
│
├── src/                         ← Keep existing UI
│   ├── main.js
│   ├── tasks.js
│   └── ...
│
├── backend/                     ← New Python backend
│   ├── main.py                  # FastAPI app (replaces serve.mjs)
│   ├── config.py
│   ├── langgraph/               # State graphs & nodes
│   ├── mcp/                     # MCP tool management
│   ├── sandbox/                 # Tool execution isolation
│   ├── services/                # Brain, roster, skills loaders
│   ├── api/                     # Route handlers
│   └── tests/
│
└── brain/                       ← Kept as-is (your notes)
    └── Agents Office/
        ├── skills/
        ├── feedback/
        └── routines.json
```

---

## Quick Decision Checklist

- [ ] Do you have Python 3.11+?
- [ ] Comfortable with async/await?
- [ ] Want to start with single-agent first?
- [ ] Planning to use MCP servers (Gmail, Slack, Notion)?
- [ ] Need sandboxing from day 1, or later?

**If all yes:** Start with IMPLEMENTATION_GUIDE.md, use subprocess sandbox

**If sandbox is a must:** Start with SANDBOXING_GUIDE.md, pick Docker

**If you want to understand first:** Start with LANGGRAPH_MIGRATION.md

---

## Next Steps

1. **Read** LANGGRAPH_MIGRATION.md (15 min)
2. **Skim** IMPLEMENTATION_GUIDE.md code (15 min)
3. **Decide** sandbox approach using SANDBOXING_GUIDE.md (10 min)
4. **Create** Python project structure
5. **Implement** core graph (load_context → route → run_agent)
6. **Test** with single agent
7. **Add** tools + MCP integration
8. **Layer** on sandboxing
9. **Extend** to teams + routines

---

## What You're Building

A **drop-in replacement** for agents-office backend that:

- ✓ Runs the same office UI (no frontend changes)
- ✓ Executes 35 agents in 6 departments
- ✓ Reads/writes same file formats (agents.json, skills, feedback, routines.json)
- ✓ Uses same MCP servers (Gmail, Slack, Notion, etc.)
- ✓ Sandboxes tool execution (safe for demos + production)
- ✓ Orchestrates teams (parallel agent work)
- ✓ Schedules routines (timetable-driven tasks)
- ✓ Integrates with your brain (Obsidian vault)

But with:
- ✓ Explicit state graphs (testable, debuggable)
- ✓ Proper checkpointing (recovery from crashes)
- ✓ Built-in approval gates (no polling)
- ✓ Audit trail (compliance-ready)
- ✓ Scales horizontally (Kubernetes-ready)

---

## Support & References

**LangGraph Docs:** https://docs.langchain.com/langgraph
**MCP Docs:** https://modelcontextprotocol.io
**Original agents-office:** https://github.com/ajsahni/agents-office

**In this folder:**
- agents-office-langgraph/LANGGRAPH_MIGRATION.md — Architecture
- agents-office-langgraph/IMPLEMENTATION_GUIDE.md — Code
- agents-office-langgraph/SANDBOXING_GUIDE.md — Security
- agents-office-langgraph/README_MIGRATION.md — This file

---

## One More Thing

**This is your demo.** The goal is:

1. Understand how to build this (read the guides)
2. Own the architecture (you built it, not just using it)
3. Extend it (add your own nodes, custom logic)
4. Pitch to customers (sandboxing + multi-agent = serious)

You now have a complete, production-capable blueprint. Everything is modular — start with subprocess sandbox, swap to Docker/Kubernetes when you need it.

Good luck! 🚀
