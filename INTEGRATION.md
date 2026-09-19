# Unified Project Integration

**Status:** Phase 1-2 Backend + v3.6 Frontend - Single Repository

## Structure

```
agent-office-yekdast/              (Main repository)
├── backend/                        (Python LangGraph backend)
│   ├── main.py                     (FastAPI server, port 8000)
│   ├── langgraph/                  (Graph orchestration)
│   ├── services/                   (Config, roster, brain, checkpoint, executor)
│   ├── tests/                      (34 tests, all passing)
│   └── requirements.txt            (Python dependencies)
│
├── frontend/                       (Original agents-office v3.6)
│   ├── serve.mjs                   (Node.js HTTP server, port 4520)
│   │   └── [MODIFIED] Proxy layer for Python backend
│   ├── src/                        (Three.js 3D interface)
│   ├── package.json                (Node dependencies)
│   └── office.config.json          (Roster, brain config)
│
├── .git/                           (Single git repository)
├── requirements.txt                (Python)
└── package.json                    (Frontend - Node.js)
```

## Migration Changes

### Frontend (serve.mjs)
- Added environment variable: `USE_PYTHON_BACKEND=true`
- Added proxy layer: `proxyToPython()` function
- Task creation endpoints proxy to Python backend when enabled
- Task status/approval endpoints proxy to Python backend when enabled
- Falls back to local Claude CLI/SDK when `USE_PYTHON_BACKEND=false`

### Backend (Python)
- FastAPI server on port 8000
- CORS configured for frontend (4520, 3000)
- Task execution through LangGraph
- State persistence (checkpointing)
- All 34 tests passing

## Running the Unified Stack

### Option 1: Python Backend (Phases 2-3)

**Terminal 1 - Backend:**
```bash
cd D:\Projects\agent-office-yekdast
python -m backend.main
# Output: 🚀 Starting on http://localhost:8000
```

**Terminal 2 - Frontend:**
```bash
cd D:\Projects\agent-office-yekdast\frontend
npm install    # first time
USE_PYTHON_BACKEND=true npm start
# Output: Agents Office ... → http://localhost:4520
# [MIGRATION] Using Python LangGraph backend at http://localhost:8000
```

### Option 2: Local Claude (Original Mode)

**Terminal 1 - Frontend:**
```bash
cd D:\Projects\agent-office-yekdast\frontend
USE_PYTHON_BACKEND=false npm start
# Uses Claude CLI or SDK (legacy mode)
```

## Integration Points

### API Proxying
When `USE_PYTHON_BACKEND=true`:
- `POST /api/tasks` → Python backend task creation
- `GET /api/tasks/{id}` → Python backend task status
- `POST /api/tasks/{id}/approve` → Python backend approval
- `POST /api/tasks/{id}/reject` → Python backend rejection

### Fallback Behavior
- If Python backend unavailable, returns 500 with error
- Local Claude CLI/SDK still works when `USE_PYTHON_BACKEND=false`
- All other endpoints (agents, brain, skills, etc.) run locally

## Testing Integration

### Verify Backend Ready
```bash
curl http://localhost:8000/api/health
# Should return: {"status":"ok","version":"3.6.0-py",...}
```

### Create Test Task (with Python Backend)
```bash
curl -X POST http://localhost:4520/api/tasks \
  -H "Content-Type: application/json" \
  -d '{"dept":"marketing","text":"Create brief","model":"sonnet","effort":"low"}'
```

### Expected Flow
```
Frontend (4520) 
  → POST /api/tasks
  → Proxy to Backend (8000)
  → LangGraph execution
  → Return task_id + status
  → Frontend displays status
```

## Deployment Checklist

- [x] Original codebase moved to `frontend/`
- [x] Python backend in `backend/`
- [x] Single git repository (removed .git from frontend)
- [x] Proxy layer added to serve.mjs
- [x] CORS configured in Python backend
- [x] Environment variable for backend selection
- [x] All tests passing (34/34)
- [x] Cache cleaned (processes, node_modules, pytest, __pycache__)
- [x] Backend running on port 8000 (FastAPI/LangGraph)
- [x] Frontend starting on port 4520 (USE_PYTHON_BACKEND=true)
- [x] All task operations routed to Python backend
- [ ] Live UI testing and customization (in progress)

## What's Next

### Phases 3-5 (Planned)
1. **Phase 3:** Claude API integration (real agent execution)
2. **Phase 4:** Team execution (parallel specialists)
3. **Phase 5:** Routines & scheduling

### No Changes Needed
- Original frontend (agents-office) code untouched
- Brain vault structure preserved
- Roster system works with both backends

## Troubleshooting

### Backend Connection Failed
```
Error: Backend unavailable
```
- Ensure Python backend is running on port 8000
- Check `PYTHON_BACKEND_URL` env var
- Verify CORS headers in Python backend

### Frontend Won't Start
```
npm: command not found
```
- Install Node.js 18+ first
- Run `npm install` in frontend/ folder

### Proxy Returns 500
- Check Python backend logs for execution errors
- Verify task parameters (department, text, model, effort)
- See VALIDATION_PHASES.md for debugging

## Environment Variables

```bash
# Frontend (.env or export before npm start)
USE_PYTHON_BACKEND=true|false      # Route to Python (default: false)
PYTHON_BACKEND_URL=http://...      # Custom backend URL (default: localhost:8000)

# Backend (existing .env)
ANTHROPIC_BASE_URL=http://...
ANTHROPIC_AUTH_TOKEN=sk-...
```

---

**Ready to test:** Run Python backend + Frontend with `USE_PYTHON_BACKEND=true`
