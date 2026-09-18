# Quick Reference Guide

**Read this first. Details in IMPLEMENTATION_PLAN.md**

---

## Overview

- **Project:** Agents Office v3.6.0-py (Python rewrite)
- **Duration:** 6 weeks
- **Phases:** 8 (Bootstrap → Production)
- **Files to write:** ~20 Python files + tests

---

## Phase 1: Bootstrap (1 Day)

```bash
# Install
python3.11 -m venv venv
pip install fastapi uvicorn pydantic anthropic langgraph langchain

# Start services
docker-compose up -d

# Verify
curl http://localhost:8000/api/health
open http://localhost:16686  # Jaeger traces
```

**What's running:**
- Backend: 8000
- PostgreSQL: 5432
- Redis: 6379
- Jaeger UI: 16686
- Prometheus: 9090

---

## Phase 2: Core Graph (Week 1)

**Create 5 files:**

1. **`backend/langgraph/state.py`**
   - Define `OfficeState` (task status, context, approval, team, routine)

2. **`backend/langgraph/nodes.py`**
   - `load_context()` — Load brain notes + agent metadata
   - `route_agent()` — Pick best agent
   - `run_agent()` — Execute with Claude + tools
   - `check_approval()` — Decide if needs human approval
   - `wait_for_approval()` — Poll for /approve or /reject
   - `save_deliverable()` — Write to brain

3. **`backend/langgraph/graphs.py`**
   - Build StateGraph with 6 nodes + conditional routing

4. **`backend/api/tasks.py`**
   - `POST /api/tasks` — Create & execute task
   - `GET /api/tasks/{id}` — Get status
   - `POST /api/tasks/{id}/approve` — Approve
   - `POST /api/tasks/{id}/reject` — Reject + learn

5. **`backend/tests/test_*.py`**
   - Unit tests for nodes
   - API tests for routes
   - Integration tests

**Success:** Task runs end-to-end, visible in Jaeger traces.

---

## Phase 3: Knowledge Base (Week 1-2)

**Create 1 file:**

- **`backend/services/knowledge_base.py`**
  - Store conversation history (JSONL per task)
  - Store learned rules (markdown)
  - Retrieve for context

**Integrate:**
- Load KB history in `load_context`
- Store conversation in `run_agent`
- Learn from rejection in reject endpoint

**Success:** Learned rules appear in next task prompt.

---

## Phase 4: Team Execution (Week 2)

**Add 3 nodes:**

- `team_plan()` — Lead splits task into pieces
- `team_execute()` — Run teammates in parallel (asyncio.gather)
- `team_merge()` — Lead combines results

**Update:**
- StateGraph routing (agent vs team path)
- POST /api/tasks to accept `is_team_task: true`

**Success:** Parallel execution faster than serial.

---

## Phase 5: Routines (Week 3)

**Create:**
- `backend/langgraph/routines.py` — Separate RoutineState graph
- `backend/services/scheduler.py` — Server-side clock (checks every minute)

**Features:**
- Parse `when` format (weekly, daily, hourly, etc.)
- Fire routine at scheduled time
- Catch up if office was offline (run once)
- Approval gate for outbound actions

**Success:** Routine fires at right time.

---

## Phase 6: Advanced (Week 4)

**Implement:**
- `backend/services/skills.py` → Load .md files from brain
- Chat endpoint → Agent responds in persona
- Brain graph rebuild → Wiki-link analysis

**Success:** Chat works, skills load, graph updates.

---

## Phase 7: Sandboxing (Week 5)

**Create:**
- `backend/sandbox/executor.py` — Docker container executor
- `backend/observability/audit.py` — Immutable audit logging

**Features:**
- Tool calls run in 256MB container (30s timeout)
- Permission whitelist per agent
- Audit trail (who called what when)

**Success:** Container escape fails safely.

---

## Phase 8: Production (Week 6)

**Add:**
- PostgreSQL checkpointing (state survives crashes)
- Redis caching (faster lookups)
- Prometheus metrics (request latency, tool success, etc.)

**Success:** Metrics visible, no data loss on restart.

---

## Git Workflow (All Phases)

```bash
# Start week
git checkout develop
git pull origin develop

# Create feature branch
git checkout -b feature/langgraph-core-implementation

# Code
vim backend/langgraph/state.py

# Commit (pre-commit hooks auto-test)
git add backend/langgraph/state.py
git commit -m "feat(langgraph): add OfficeState schema

- Define state for all task types
- Support approval, KB, team, routine

Co-Authored-By: Claude Haiku 4.5 <noreply@anthropic.com>"

# Hooks run automatically:
# ✓ Black formatter
# ✓ Flake8 linting
# ✓ Mypy type check
# ✓ Pytest tests

# Push when ready
git push origin feature/langgraph-core-implementation

# Create PR on GitHub, merge when approved
```

**Keys:**
- Conventional commit format: `type(scope): message`
- Hooks block bad code (formatting, tests, types)
- Only push to feature branches (never directly to develop/main)

---

## Testing

```bash
# All tests
pytest backend/tests -v --cov=backend

# Specific test
pytest backend/tests/test_nodes.py::test_load_context -v

# Watch mode
pytest backend/tests --tb=short -x  # stop on first failure
```

**Coverage target:** 80%+ per phase

---

## Observability

### Traces (Jaeger)
http://localhost:16686
- Every node execution visible
- Tool calls traced
- Latency measured

### Logs (Structured)
```bash
docker-compose logs backend | grep task_id
```
- Timestamp, task ID, agent ID, operation, result

### Metrics (Prometheus)
http://localhost:9090
- Request latency distribution
- Tool success rate
- Tasks per department

---

## API Endpoints (All Phases)

| Method | Endpoint | Body | Response |
|--------|----------|------|----------|
| POST | /api/tasks | `{department, text, model, effort}` | `{task_id, status}` |
| GET | /api/tasks/{id} | — | `{task_id, status, deliverable, ...}` |
| POST | /api/tasks/{id}/approve | — | `{approved: true}` |
| POST | /api/tasks/{id}/reject | `{feedback}` | `{rejected: true}` |
| POST | /api/tasks/{id}/messages | `{message}` | `{response}` |
| GET | /api/routines | — | `[routine1, routine2, ...]` |
| POST | /api/routines | `{department, text, when}` | `{routine_id}` |
| GET | /api/health | — | `{status, version}` |

**Frontend (unchanged):**
- http://localhost:4520 (v3.6 UI)
- Same API, only backend swaps

---

## Common Commands

```bash
# Services
docker-compose up -d        # Start
docker-compose logs -f      # View logs
docker-compose down         # Stop
docker-compose down -v      # Stop + remove volumes

# Testing
pytest backend/tests -v     # Run tests
black backend/              # Auto-format
flake8 backend/             # Lint

# Git
git checkout -b feature/name  # New branch
git add backend/              # Stage files
git commit -m "..."           # Commit (hooks run)
git push origin feature/name   # Push
git log --oneline -10         # View history
```

---

## Files to Create (By Phase)

| Phase | Files |
|-------|-------|
| 1 | docker-compose.yml, Dockerfile, backend/main.py, backend/config.py |
| 2 | state.py, nodes.py, graphs.py, api/tasks.py, tests/test_*.py |
| 3 | services/knowledge_base.py |
| 4 | (Add 3 nodes to nodes.py, update graphs.py) |
| 5 | langgraph/routines.py, services/scheduler.py |
| 6 | services/skills.py, api/chat.py, (integrate) |
| 7 | sandbox/executor.py, observability/audit.py |
| 8 | (Add checkpointer, Redis, metrics) |

---

## Success Metrics

| Phase | You'll Know It Works When... |
|-------|------------------------------|
| 1 | `curl http://localhost:8000/api/health` returns 200 |
| 2 | POST /api/tasks → Claude call visible in traces → saves to brain |
| 3 | User sends `revise: ...` → next task has learned rule in prompt |
| 4 | 4 agents work in parallel (asyncio.gather, wall-clock time faster) |
| 5 | Routine fires at exact minute, catches up if office offline |
| 6 | Agent chats back in persona, skills in prompt |
| 7 | Tool call runs in container, audit logged, no escape |
| 8 | Prometheus shows metrics, restart doesn't lose state |

---

## Troubleshooting

| Problem | Fix |
|---------|-----|
| `Black formatting failed` | `black backend/` |
| `Flake8 errors` | Review output, fix manually |
| `Tests fail` | `pytest backend/tests -v` to see failures |
| `Docker won't start` | `docker-compose down -v`, then `docker-compose up -d` |
| `Claude calls fail` | Check `ANTHROPIC_API_KEY` env var |
| `Traces not showing` | `docker-compose logs jaeger`, verify running |
| `Brain notes empty` | Check `./brain/` path exists |
| `Commit blocked` | Pre-commit hook failed; fix + retry |

---

## Next Steps

1. **Read:** IMPLEMENTATION_PLAN.md (full details)
2. **Do:** Phase 1 (Bootstrap) today
3. **Do:** Phase 2 (Core Graph) this week
4. **Monitor:** Traces in Jaeger, tests passing
5. **Continue:** Phases 3-8 weekly

---

## Key Concepts

**StateGraph:** DAG of nodes + conditional edges (LangGraph)

**OfficeState:** Single dict holding all task state (no mutation)

**Nodes:** Async functions that take state → return updated state

**Conditional edges:** Route based on state (e.g., needs approval?)

**Knowledge Base:** JSONL history + markdown rules per agent (persistent)

**MCP Tools:** Claude calls tools → agent executes → result back

**Sandboxing:** Tool calls run in Docker, isolated from host

**Audit:** Every tool call logged immutably

**Observability:** Traces (Jaeger) + logs (structured) + metrics (Prometheus)

---

**Ready?** → Open IMPLEMENTATION_PLAN.md and start Phase 1
