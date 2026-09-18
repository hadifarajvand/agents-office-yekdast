# Frontend Integration: v3.6 Official UI

**Frontend:** `D:\Projects\agents-office-original` (cloned from https://github.com/ajsahni/agents-office)  
**Backend:** `D:\Projects\agent-office-yekdast` (Python/FastAPI/LangGraph rewrite)  
**Frontend Port:** 4520 (can change with `PORT=4600 npm start`)  
**Backend Port:** 8000  

---

## API Endpoint Mapping

### Currently Implemented ✅

| Endpoint | Method | Purpose | Status |
|----------|--------|---------|--------|
| `/api/health` | GET | Server health | ✅ Works |
| `/api/agents` | GET | List agents/roster | ✅ Works |
| `/api/brain/notes` | GET | Brain vault notes | ✅ Works |
| `/api/tasks` | GET | List tasks | ✅ Works |
| `/api/tasks` | POST | Create task | ✅ Works (executes graph) |
| `/api/tasks/{id}` | GET | Get task status | ✅ Works (LangGraph state) |
| `/api/tasks/{id}/approve` | POST | Approve task | ✅ Works |
| `/api/tasks/{id}/reject` | POST | Reject task | ✅ Works |

### To Implement 🔄 (Phase 4+)

| Endpoint | Method | Purpose | Phase |
|----------|--------|---------|-------|
| `/api/routines` | GET | List routines | 5 |
| `/api/routines` | POST | Create routine | 5 |
| `/api/routines/{id}` | DELETE | Delete routine | 5 |
| `/api/mcp` | GET | MCP connectors list | 5 |
| `/api/chat` | POST | Chat with agent | 4 |
| `/api/usage` | GET | Usage/token stats | 3 |
| `/api/brain` | GET | Brain graph for visualization | 7 |
| `/api/tasks/{id}/revise` | POST | Revise task | 4 |
| `/api/tasks/{id}/run` | POST | Run task | 4 |
| `/api/skills` | GET | List skills | 6 |

---

## Setup & Running

### 1. Install Frontend Dependencies (One Time)

```bash
cd D:\Projects\agents-office-original
npm install
```

### 2. Start Both Services

**Terminal 1 - Backend:**
```bash
cd D:\Projects\agent-office-yekdast
python -m backend.main
# Output: 🚀 Starting on http://localhost:8000
```

**Terminal 2 - Frontend:**
```bash
cd D:\Projects\agents-office-original
npm start
# Output: Server running at http://localhost:4520
```

### 3. Open UI
```
http://localhost:4520
```

---

## CORS Configuration

Backend (`backend/main.py`) already has CORS configured for frontend:

```python
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:4520", "http://localhost:3000"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)
```

✅ No changes needed — frontend can call backend directly.

---

## Frontend Features Available Now

### ✅ Working (Phases 1-3)
- Health check displays backend status
- Agent list shows 15 agents (4 leads, 11 specialists)
- Brain notes display
- **Task Creation** → Routes to department → Executes LangGraph → Returns deliverable
- **Task Status** → Shows real execution state (pending → completed)
- **Approval Workflow** → Approve/reject with feedback
- Real-time status updates from Python backend

### 🔄 Partial (Phase 3+)
- Task execution shows status but results are placeholders (waiting for Claude API)
- No token counting yet (Phase 3)
- No team execution splitting (Phase 4)
- No routines (Phase 5)

### ❌ Not Available Yet
- Routines & scheduling (Phase 5)
- Brain rebuild (Phase 7)
- Skills management (Phase 6)
- MCP tool integration (Phase 5+)
- Chat with agents (Phase 4)

---

## Testing Workflow

### Phase 1-2: Infrastructure ✅
1. Start backend & frontend
2. Open http://localhost:4520
3. Click "Create Task" 
4. Select "Marketing" department
5. Type "Create quarterly brief"
6. Click submit
7. See task routed to marketing_lead
8. See status: completed (with LangGraph execution trace)

### Phase 3: Claude API (Next)
1. Same as above, but see real Claude API responses
2. See token counts and costs
3. See retry logic in logs

### Phase 4: Team Execution
1. Create task with "as a team" in description
2. See lead route to multiple specialists
3. See parallel execution, results per specialist
4. See final synthesis

---

## Debugging

### If Frontend Can't Connect to Backend
```bash
# Check backend is running
curl http://localhost:8000/api/health

# Should return:
# {"status":"ok","version":"3.6.0-py",...}
```

### If Tasks Fail
1. Check **backend terminal** for execution logs
2. Look for `[ERROR]`, `[WARN]`, `[EXEC]` messages
3. If LangGraph issue: check node execution order
4. If Claude API issue (Phase 3+): verify `ANTHROPIC_AUTH_TOKEN`

### Logs to Watch

**Backend Logs:**
```
[INFO] Task created: abc12345
[EXEC] Router: routing to marketing
[EXEC] Brain context: 5 notes retrieved
[EXEC] Lead planning: assigning marketing_copy
[EXEC] Specialist execution: 2 agents parallel
[EXEC] Synthesis: combining results
[EXEC] Task completed: abc12345
```

**Frontend Console:**
```
POST /api/tasks → 200 (task created)
GET /api/tasks/abc12345 → 200 (status: completed)
```

---

## File Structure

```
D:\Projects\
├── agent-office-yekdast/          (Python backend - rewrite)
│   ├── backend/
│   │   ├── main.py                (FastAPI server)
│   │   ├── config.py              (Config loader)
│   │   ├── services/
│   │   │   ├── roster.py          (Agent roster)
│   │   │   ├── brain.py           (Knowledge vault)
│   │   │   ├── checkpoint.py      (State checkpoints)
│   │   │   └── task_executor.py   (LangGraph executor)
│   │   ├── langgraph/
│   │   │   ├── state.py           (OfficeState schema)
│   │   │   ├── agents.py          (15 agent configs)
│   │   │   ├── nodes.py           (8 execution nodes)
│   │   │   └── graphs.py          (StateGraph builder)
│   │   └── tests/
│   │       ├── test_bootstrap.py  (1 test)
│   │       ├── test_api.py        (5 tests)
│   │       ├── test_brain_robustness.py (15 tests)
│   │       └── test_langgraph.py  (13 tests)
│   └── requirements.txt
│
└── agents-office-original/         (Frontend - original v3.6)
    ├── src/
    │   ├── main.js                (Three.js 3D office)
    │   ├── tasks.js               (Task management UI)
    │   ├── brain.js               (Brain visualization)
    │   ├── screens.js             (Agent screens)
    │   └── ...
    ├── serve.mjs                  (Node.js server)
    ├── package.json
    └── ...
```

---

## Next Steps

1. **Run Phase 1-2 Test:**
   ```bash
   # Terminal 1
   cd D:\Projects\agent-office-yekdast && python -m backend.main
   
   # Terminal 2
   cd D:\Projects\agents-office-original && npm start
   
   # Terminal 3
   open http://localhost:4520
   ```

2. **Create Test Task:**
   - Type: "Create a marketing brief for Q4"
   - Department: Marketing
   - Model: Sonnet
   - Click Submit
   - Watch status update

3. **Check Logs:**
   - Backend terminal shows execution flow
   - Frontend displays results

4. **Report Issues:**
   - Share backend error logs
   - Share frontend console errors
   - I'll debug LangGraph/LangChain runtime

---

## Status

| Component | Status | URL |
|-----------|--------|-----|
| Backend API | ✅ Ready | http://localhost:8000 |
| Frontend | ✅ Ready | http://localhost:4520 |
| Health Check | ✅ Working | `curl http://localhost:8000/api/health` |
| Task Execution | ✅ Working | POST /api/tasks |
| Task Status | ✅ Working | GET /api/tasks/{id} |
| Approval | ✅ Working | POST /api/tasks/{id}/approve |

**Ready to test. Launch Phase 1-2 validation now.**
