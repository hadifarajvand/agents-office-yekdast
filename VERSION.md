# Version History

## Current: 3.6.0-py (Python Rewrite)

**Status:** Development
**Branch:** develop
**Started:** 2026-09-18

### Features Planned

#### Week 1: Core Graph ✅
- [x] OfficeState schema
- [x] 6-node LangGraph implementation
- [ ] FastAPI routes (POST /api/tasks, GET /api/tasks/{id})
- [ ] Agent knowledge base
- [ ] Observability infrastructure

#### Week 2: Team Execution
- [ ] Team planning node
- [ ] Parallel teammate execution
- [ ] Piece assembly (lead merges)
- [ ] Coordination notes

#### Week 3: Routines & Scheduling
- [ ] RoutineState graph
- [ ] Timetable parsing
- [ ] Catch-up logic
- [ ] Approval gates

#### Week 4: Advanced
- [ ] Learning system (revise:)
- [ ] Skills integration
- [ ] Chat endpoint
- [ ] Brain graph rebuild

#### Week 5: Sandboxing
- [ ] Docker executor
- [ ] Permission whitelist
- [ ] Audit logging
- [ ] Security tests

#### Week 6: Production
- [ ] PostgreSQL checkpointing
- [ ] Redis caching
- [ ] Prometheus metrics
- [ ] Load testing

---

## Previous: 3.6.0 (Node.js)

**Status:** Stable
**Branch:** n/a (original repo)
**Frontend:** Unchanged (reused)

### v3.6 Features (All Ported to Python)
- 35 agents across 6 departments
- MCP server integration (Gmail, Slack, Notion, etc.)
- Brain vault (wiki-link graph)
- Skills & briefs per agent
- Learned rules from feedback
- Routines (timetable tasks)
- Agent Teams (parallel execution)
- Approval workflows
- Chat with agents
- Calendar (tasks + routines)

---

## Breaking Changes (v3.6.0-py)

**None planned.** API remains identical, only backend swaps from Node.js to Python.

Frontend: `dist/command-centre-v2.html` unchanged
Config: `office.config.json`, `office.agents.json` unchanged
Brain: `brain/` folder structure unchanged
