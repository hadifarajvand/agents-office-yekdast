# How to Test Agents Office v3.6.0-py

**Total Time:** ~15 minutes  
**What You'll Get:** Fully working Phase 1 + Phase 2 infrastructure  
**Phases Included:** Bootstrap + LangGraph Orchestration  

---

## STEP 1: Prepare Environment (2 minutes)

```bash
# Navigate to project
cd D:\Projects\agent-office-yekdast

# Copy configuration template
copy .env.example .env

# Edit .env with your local Claude settings:
# ANTHROPIC_BASE_URL=http://127.0.0.1:20128/v1
# ANTHROPIC_AUTH_TOKEN=sk-your-token-here
notepad .env
```

## STEP 2: Verify Project Structure (1 minute)

```bash
# Check all required files exist
dir brain                    # Should exist
dir backend\langgraph        # Should have: state.py, agents.py, nodes.py, graphs.py
dir backend\tests            # Should have test files
type requirements.txt        # Check dependencies
type docker-compose.yml      # Check services
```

## STEP 3: Install Dependencies (3 minutes)

```bash
# Python 3.11+ required
python --version

# Install all dependencies
pip install -r requirements.txt

# Verify installations
python -c "import fastapi, langgraph, anthropic; print('OK')"
```

## STEP 4: Run Unit Tests (2 minutes)

```bash
# Run all tests
pytest backend/tests/ -v

# Expected: 21 PASSED
# If any fail, check error output
```

## STEP 5: Start the Server (Background)

**Terminal 1:**
```bash
# Start backend server
python -m backend.main

# Expected output:
# [INFO] Agents Office Agents Office
# [INFO] Backend: FastAPI on port 8000
# [INFO] Brain: ...
# [INFO] Model: sonnet
# [INFO] Agents: 2 (1 customized, 0 with briefs)
# [INFO] Brain: 0 notes
# [START] Server initialized
# 🚀 Starting on http://localhost:8000
# 📖 Docs at http://localhost:8000/docs
```

**Keep this terminal running!**

## STEP 6: Verify Server Health

**Terminal 2 (New):**
```bash
# Check server is running
curl http://localhost:8000/api/health

# Expected response:
# {
#   "status": "ok",
#   "version": "3.6.0-py",
#   "backend": "fastapi",
#   "model": "sonnet",
#   "agents": 2,
#   "notes": 0,
#   "timestamp": "2026-09-18T..."
# }
```

## STEP 7: Test Core APIs

```bash
# 1. List all agents
curl http://localhost:8000/api/agents

# 2. List brain notes
curl http://localhost:8000/api/brain/notes

# 3. Create a task
curl -X POST http://localhost:8000/api/tasks ^
  -H "Content-Type: application/json" ^
  -d "{ \"department\": \"marketing\", \"text\": \"Create Q4 brief\", \"model\": \"sonnet\", \"effort\": \"low\" }"

# Expected response:
# {
#   "task_id": "abc12345",
#   "status": "pending",
#   "department": "marketing",
#   "created_at": 1726755987450
# }

# 4. Get task status
curl http://localhost:8000/api/tasks/abc12345

# 5. Approve task
curl -X POST http://localhost:8000/api/tasks/abc12345/approve

# Expected response:
# { "approved": true }
```

## STEP 8: View Interactive Docs

Open in browser:
```
http://localhost:8000/docs
```

You'll see:
- All endpoints listed
- Try-it-out interface
- Request/response examples
- Schema definitions

## STEP 9: Test LangGraph Integration

**Terminal 2:**
```bash
# Run Python script to test graph execution
python -c "
from backend.langgraph.graphs import office_graph
from backend.langgraph.state import OfficeState
import time

# Create initial state
state = OfficeState(
    task_id='test-123',
    created_by='user@example.com',
    created_at=time.time(),
    task_text='Create marketing brief for Q4',
    department='marketing',
    model='sonnet',
    effort='low',
    status='pending',
    assigned_lead=None,
    assigned_agents=[],
    brain_context=[],
    brain_context_query=None,
    messages=[],
    working_memory={},
    specialist_results={},
    deliverable=None,
    errors=[],
    retry_count=0,
    last_error=None,
    used_tools=[],
    total_tokens=0,
    cost_usd=0.0,
    start_time=time.time(),
    last_checkpoint=time.time(),
    approval_status='pending',
    approval_feedback=None,
    user_feedback=None,
    version=1,
    checkpoint_node=None,
)

# Execute graph
result = office_graph.invoke(state)

# Print results
print(f'Status: {result[\"status\"]}')
print(f'Lead Agent: {result[\"assigned_lead\"]}')
print(f'Specialists: {result[\"assigned_agents\"]}')
print(f'Messages: {len(result[\"messages\"])}')
"
```

## STEP 10: Docker Deployment (Optional)

```bash
# Option 1: Full stack with Docker Compose
docker-compose up

# Option 2: Just backend in Docker
docker build -t agents-office .
docker run -p 8000:8000 -e PORT=8000 agents-office

# Verify
curl http://localhost:8000/api/health
```

---

## What You Should See

### Phase 1: Bootstrap ✅
- [x] Server starts on port 8000
- [x] Configuration loads (local Claude settings)
- [x] Roster loads (2+ agents)
- [x] Brain loads (0 notes initially)
- [x] Health endpoint responds
- [x] All 21 tests pass

### Phase 2: LangGraph ✅
- [x] StateGraph compiles without errors
- [x] 15 agent configs loaded
- [x] 8 execution nodes defined
- [x] Task routing works
- [x] Brain context retrieval works
- [x] Specialist execution (placeholder, non-blocking)
- [x] Approval workflow ready

---

## Troubleshooting

### Error: "Port 8000 already in use"
```bash
# Use different port
set PORT=8001
python -m backend.main
```

### Error: "ModuleNotFoundError: No module named 'langgraph'"
```bash
# Reinstall dependencies
pip install -r requirements.txt --upgrade
```

### Error: "Connection refused" (curl fails)
```bash
# Make sure server is running in Terminal 1
# Check it's listening on port 8000
netstat -an | find "8000"
```

### Tests fail
```bash
# Clear cache and reinstall
rmdir /s /q backend\__pycache__
pip install -r requirements.txt --force-reinstall
pytest backend/tests/ -v
```

---

## What's NOT Included (Phase 3+)

These are fully designed but not yet implemented:
- [ ] Claude API calls (agents don't actually execute yet - placeholders)
- [ ] PostgreSQL state checkpointing
- [ ] Real retry logic (5 retries + escalate)
- [ ] Brain write queue + versioning
- [ ] LangChain ReAct for lead decisions
- [ ] MCP tool integration
- [ ] Advanced observability

**All the infrastructure is ready for Phase 3** - it's just the Claude API integration and advanced features that are placeholders.

---

## Next Steps After Testing

1. **Verify Everything Works:** Run through all 10 steps above
2. **Explore API Docs:** Open http://localhost:8000/docs
3. **Review Code:** Check `backend/langgraph/` for architecture
4. **Plan Phase 3:** When ready, integrate Claude API calls

---

## Success Criteria

✅ You've successfully deployed Agents Office v3.6.0-py when:

1. Server starts without errors
2. Health endpoint returns `"status": "ok"`
3. All 21 tests pass
4. Task creation returns a `task_id`
5. Task status can be retrieved
6. Graph executes without errors
7. Docker compose runs (optional)

**Expected time to full success:** 15 minutes

---

## Support

If something doesn't work:
1. Check DEPLOYMENT_GUIDE.md (troubleshooting section)
2. Check server logs (Terminal 1) for error messages
3. Run tests individually: `pytest backend/tests/test_api.py -v`
4. Review error messages - they're very specific

**Everything is designed to work. If it doesn't, the error message will tell you exactly what to fix.**

---

**Ready? Start with STEP 1!**
