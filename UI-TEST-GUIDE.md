# UI Integration Test - Live Testing Guide

## Status: ✅ Both Services Running

### Services
- **Backend:** http://localhost:8000 (Python/FastAPI/LangGraph)
- **Frontend:** http://localhost:4520 (Node.js/Three.js)
- **API Docs:** http://localhost:8000/docs

---

## Manual Testing Workflow

### 1. **Initial Load**
- [ ] Open http://localhost:4520 in your browser
- [ ] Wait for 3D isometric office to render
- [ ] Verify you can see the department pods
- [ ] Check the top bar shows available agents

**Expected:** Clean 3D office with colorful department areas (Marketing, Sales, Support, etc.)

---

### 2. **Create Task Through UI**
- [ ] Look for the task creation area (usually top-right or command bar)
- [ ] Select **Department: Marketing**
- [ ] Enter task text: `Create a quarterly marketing brief`
- [ ] Set Model: **Sonnet** (or default)
- [ ] Set Effort: **Low**
- [ ] Click **Submit** / **Create Task** button

**Expected:** 
- Task appears in the task panel
- Status shows "pending" or "in progress"
- Agent assignment displayed

---

### 3. **Monitor Execution**
- [ ] Watch the task status in the UI panel
- [ ] Check backend logs (terminal running backend)
- [ ] Look for state transitions:
  - `pending` → `doing` → `done` (or `failed` for placeholders)

**Expected Log Output:**
```
[INFO] Task created: 8fe0d223
[EXEC] Router: routing to marketing
[EXEC] Brain context: 0 notes (empty brain)
[EXEC] Lead planning: marketing_lead
[EXEC] Specialist execution...
[EXEC] Task completed
```

---

### 4. **Verify Task Status**
- [ ] Click on the task to see details
- [ ] Check "Assigned Lead" shows marketing_lead
- [ ] Verify "Status" shows completion state
- [ ] Note: Deliverable will be placeholder (Phase 3 adds Claude API)

**Expected:** Full task lifecycle visible

---

### 5. **Test Approval Workflow**
- [ ] If task shows "waiting for approval", click **Approve** button
- [ ] (Or **Reject** to test rejection flow)
- [ ] Verify status updates accordingly

**Expected:** Approval state changes reflected in UI

---

## What's Working (Phases 1-2) ✅
- [x] Task creation through UI
- [x] Routing to correct department
- [x] Agent assignment
- [x] State transitions through LangGraph
- [x] Status updates in real-time
- [x] Brain context retrieval
- [x] Approval workflow

## What's Not Yet (Phase 3+) ⏳
- [ ] Claude API responses (currently placeholders)
- [ ] Actual task execution results
- [ ] Real token counting
- [ ] Team execution (parallel agents)
- [ ] Routines/scheduling

---

## Troubleshooting

### "Cannot connect to backend"
- Verify backend is running: `curl http://localhost:8000/api/health`
- Check if port 8000 is in use: `netstat -an | find "8000"`

### "3D office not rendering"
- Check browser console (F12) for WebGL errors
- Try a modern browser (Chrome, Firefox, Safari)
- Verify Three.js loaded: check Network tab in DevTools

### "Task creation fails"
- Check backend logs for error messages
- Verify `USE_PYTHON_BACKEND=true` is set
- Test API directly: `curl -X POST http://localhost:8000/api/tasks ...`

### "Status doesn't update"
- Page may need refresh (F5)
- Check browser console for fetch errors
- Backend should show task execution logs

---

## API Testing (Direct)

If UI testing shows issues, test API directly:

```bash
# Create task
curl -X POST http://localhost:8000/api/tasks \
  -H "Content-Type: application/json" \
  -d '{"department":"marketing","text":"Test brief","model":"sonnet","effort":"low"}'

# Get task status
curl http://localhost:8000/api/tasks/{task_id}

# Approve task
curl -X POST http://localhost:8000/api/tasks/{task_id}/approve
```

---

## Next Steps After Testing

Once you've verified the UI works:

1. **Phase 3:** Integrate Claude API for real execution
2. **Phase 4:** Implement team execution
3. **Phase 5:** Add routines & scheduling

---

## Quick Reference

| Component | Port | Purpose |
|-----------|------|---------|
| Frontend UI | 4520 | 3D office interface |
| Backend API | 8000 | Task execution, state management |
| API Docs | 8000/docs | Interactive API reference |
| Brain Vault | `./brain/` | Knowledge base (markdown files) |

---

**Ready to test!** Follow the workflow above and report any issues.
