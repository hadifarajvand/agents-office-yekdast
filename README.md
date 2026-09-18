# Agents Office: Python + LangGraph (v3.6.0-py)

**Status:** Development  
**Branch:** develop  
**Timeline:** 6 weeks to production

---

## 🚀 Quick Start

### 1. Bootstrap Infrastructure (30 minutes)

```bash
# Install Python dependencies
python3.11 -m venv venv
source venv/bin/activate
pip install -r requirements.txt

# Start all services (Docker required)
docker-compose up -d

# Verify
curl http://localhost:8000/api/health
```

Services running:
- Backend: http://localhost:8000
- Postgres: localhost:5432
- Redis: localhost:6379
- Jaeger UI: http://localhost:16686 (traces)
- Prometheus: http://localhost:9090 (metrics)

### 2. Run Tests

```bash
pytest backend/tests -v --asyncio-mode=auto
```

### 3. Start Frontend (unchanged)

```bash
npm start
# Agents Office UI: http://localhost:4520
```

---

## 📖 Documentation

**Start here based on your role:**

### For Understanding Architecture
→ **`LANGGRAPH_MIGRATION.md`** (Architecture & design decisions)

### For Getting Started Fast
→ **`BOOTSTRAP_30MIN.md`** (Infrastructure setup + Week 1 roadmap)

### For Writing Code (Week 1)
→ **`WEEK1_LANGGRAPH_CORE.md`** (Exact code to implement)

### For Git & Version Control
→ **`GIT_WORKFLOW.md`** (Branch strategy, committing, reverting)

### For Security & Sandboxing
→ **`SANDBOXING_GUIDE.md`** (Docker isolation, permissions)

### For Contributing
→ **`CONTRIBUTING.md`** (Contribution guidelines)

### For Implementation Details
→ **`IMPLEMENTATION_GUIDE.md`** (Python templates + examples)

---

## 🏗️ Project Structure

```
agents-office/
├── .git/                        # Git repository
├── .github/
│   └── workflows/ci.yml         # GitHub Actions CI/CD
├── .githooks/                   # Pre-commit hooks (auto-test)
│   ├── pre-commit              # Runs black, flake8, mypy, pytest
│   └── commit-msg              # Validates commit messages
│
├── frontend/                    # v3.6 UI (unchanged)
│   ├── src/
│   ├── dist/
│   └── package.json
│
├── backend/                     # NEW (Python, Week 1+)
│   ├── main.py                  # FastAPI app
│   ├── config.py                # Config loading
│   ├── langgraph/               # State graphs & nodes
│   ├── mcp/                     # MCP tools (skeleton)
│   ├── sandbox/                 # Docker sandboxing (Week 5)
│   ├── services/                # Business logic
│   ├── api/                     # FastAPI routes
│   ├── observability/           # Tracing & logging
│   └── tests/                   # Full test suite
│
├── brain/                       # Your notes (Obsidian vault)
│   └── Agents Office/
│       ├── kb/                  # Agent knowledge bases
│       ├── skills/              # Skills & workflows
│       ├── feedback/            # Learned rules
│       └── routines.json        # Scheduled tasks
│
├── docker-compose.yml           # All services
├── Dockerfile                   # Backend image
├── .gitignore                   # Ignore rules
├── .gitattributes               # Line endings
│
├── VERSION.md                   # Version history
├── CONTRIBUTING.md              # Contribution guidelines
├── GIT_WORKFLOW.md              # Git guide
├── GIT_SETUP_COMPLETE.md        # Git setup verification
│
├── BOOTSTRAP_30MIN.md           # Infrastructure setup
├── WEEK1_LANGGRAPH_CORE.md      # Week 1 implementation
├── LANGGRAPH_MIGRATION.md       # Architecture
├── IMPLEMENTATION_GUIDE.md      # Code templates
├── SANDBOXING_GUIDE.md          # Security
├── README_MIGRATION.md          # Quick reference
└── README.md                    # This file
```

---

## 📋 Implementation Timeline

### Week 1: Core Graph ✅ Planning
- [ ] Implement OfficeState schema
- [ ] Build 6-node StateGraph
- [ ] Implement FastAPI routes
- [ ] Implement agent knowledge base
- [ ] Write tests
- [ ] Verify end-to-end

### Week 2: Team Execution
- [ ] Implement team planning node
- [ ] Implement parallel node execution
- [ ] Add piece assembly (lead merges)
- [ ] Add coordination notes

### Week 3: Routines & Scheduling
- [ ] Implement RoutineState graph
- [ ] Parse timetable format
- [ ] Implement catch-up logic
- [ ] Add approval gates

### Week 4: Advanced Features
- [ ] Implement learning system (revise:)
- [ ] Integrate skills files
- [ ] Add chat endpoint
- [ ] Rebuild brain graph

### Week 5: Sandboxing & Security
- [ ] Implement Docker executor
- [ ] Add permission whitelist
- [ ] Add audit logging
- [ ] Security test suite

### Week 6: Production & Polish
- [ ] PostgreSQL checkpointing
- [ ] Redis session caching
- [ ] Prometheus metrics
- [ ] Load testing
- [ ] Deploy to production

---

## 🔄 Git Workflow

**Daily workflow:**

```bash
# Start day
git checkout develop
git pull origin develop

# Create feature branch
git checkout -b feature/your-feature

# Code (hooks auto-test before commit)
git add backend/langgraph/nodes.py
git commit -m "feat(langgraph): implement feature

- Change 1
- Change 2

Co-Authored-By: Claude Haiku 4.5 <noreply@anthropic.com>"

# End day
git push origin feature/your-feature
```

**Full guide:** See `GIT_WORKFLOW.md`

---

## 🧪 Testing

### Run All Tests
```bash
pytest backend/tests -v --asyncio-mode=auto
```

### Test Specific Module
```bash
pytest backend/tests/test_nodes.py -v
```

### Test with Coverage
```bash
pytest backend/tests --cov=backend --cov-report=html
```

### Integration Tests
```bash
docker-compose up -d
pytest backend/tests/test_api.py -v
docker-compose down
```

**Note:** Pre-commit hooks run tests automatically before allowing commits.

---

## 📊 Observability

### Traces (Jaeger)
http://localhost:16686

Every task execution is traced with:
- Node start/end times
- Tool calls
- Approval gates
- Errors

### Logs (Structured)
```bash
docker-compose logs backend | grep "task_id"
```

Every operation logged with:
- Timestamp
- Task ID
- Agent ID
- Operation type
- Duration
- Result

### Metrics (Prometheus)
http://localhost:9090

Tracked:
- Request latency
- Tool success rate
- Agent execution time
- Error rate

---

## 🛠️ Development Commands

```bash
# Start services
docker-compose up -d

# View logs
docker-compose logs -f backend

# Run tests
pytest backend/tests -v

# Format code (auto)
black backend/

# Lint
flake8 backend/

# Type check
mypy backend/

# Stop services
docker-compose down

# Full reset
docker-compose down -v  # also removes volumes
```

---

## 🔐 Git Hooks

Pre-commit hooks run automatically:

1. **Black formatter** — Enforces style
2. **Flake8 linter** — Checks code quality
3. **Mypy type checker** — Validates types
4. **Pytest** — Runs all tests

If any fail, commit is blocked:
```bash
❌ Black formatting failed. Run: black backend/
```

Fix and retry:
```bash
black backend/
git commit -m "your message"
```

**Skip hooks (emergency):**
```bash
git commit --no-verify
```

---

## 🚀 Deployment

### Local Development
```bash
docker-compose up -d
npm start
```

### Production (Dockerploy)
```bash
git push origin main
# GitHub Actions builds & pushes Docker image
# Dockerploy auto-deploys to server
```

---

## 📞 Questions?

- **Git workflow?** → See `GIT_WORKFLOW.md`
- **Architecture decisions?** → See `LANGGRAPH_MIGRATION.md`
- **Sandboxing?** → See `SANDBOXING_GUIDE.md`
- **Contributing?** → See `CONTRIBUTING.md`
- **Code templates?** → See `WEEK1_LANGGRAPH_CORE.md`

---

## 📌 Key Features (v3.6.0-py)

✅ 35 agents × 6 departments  
✅ MCP server integration (Gmail, Slack, Notion, etc.)  
✅ Brain vault (Obsidian wiki-link graph)  
✅ Skills per agent (how-to workflows)  
✅ Learned rules (feedback system)  
✅ Approval workflow (human-in-the-loop)  
✅ Routines (timetable-driven tasks)  
✅ Agent Teams (parallel execution)  
✅ Chat with agents (agent personas)  
✅ Full observability (traces + logs + metrics)  
✅ Docker sandboxing (secure tool execution)  
✅ Full test suite (unit + integration + security)  

---

## 📄 License

Same as original agents-office v3.6 (PolyForm Noncommercial 1.0.0)

Free for personal and internal use. Not for resale or paid products.

---

**Ready to start?** → Begin with `WEEK1_LANGGRAPH_CORE.md`
