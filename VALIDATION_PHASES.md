# Validation Phases: UI vs Logs

## Phase-by-Phase Validation Strategy

### Phase 1: Bootstrap ✅ COMPLETE
**Validation:** Logs only (no UI needed)
- Configuration loads ✓
- Roster loads ✓
- Brain loads ✓
- Server starts ✓
- Tests pass: 21/21 ✓

```bash
# Validate with: pytest backend/tests/ -v
# Logs: [INFO] Agents Office, [INFO] Agents: X, [INFO] Brain: X notes
```

---

### Phase 2: LangGraph Core ✅ COMPLETE
**Validation:** Logs only (no UI needed)
- State schema defined ✓
- 15 agent configs loaded ✓
- 8 execution nodes built ✓
- Graph compiles ✓
- Tests pass: 34/34 ✓

```bash
# Validate with: pytest backend/tests/ -v
# Logs: Graph nodes executing, state transitions logged
```

---

### Phase 3: Claude API Integration ⏳ NEXT
**Validation:** Logs only (no UI needed)
- Claude API calls execute
- Agent responses received
- Token counting works
- Retry logic functions (5 retries + escalate)

```bash
# Validate with:
pytest backend/tests/test_execution.py -v

# Logs to check:
# [EXEC] Calling agent: {agent_id}
# [RESPONSE] tokens={X}, cost=${Y}
# [RETRY] attempt {N} for {agent_id}
# [ESCALATE] escalating to lead
```

---

### Phase 4: Team Execution ⏳ REQUIRES UI
**Validation:** UI Testing Required
- Lead selects specialists (LangChain ReAct)
- Parallel specialist execution visible
- Results synthesized and displayed
- Brain updates queued

```
UI Checklist:
- [ ] Task routing shows department
- [ ] Lead assignments visible
- [ ] Specialist results displayed
- [ ] Synthesis shows final deliverable
- [ ] Status updates in real-time
```

---

### Phase 5: Routines & Scheduling ⏳ REQUIRES UI
**Validation:** UI Testing Required
- Timetable creation in UI
- Recurring task setup
- Catch-up logic triggered
- Task history visible

```
UI Checklist:
- [ ] Create routine form works
- [ ] Schedule dropdown shows times
- [ ] Recurring checkbox functional
- [ ] Routine list displays all
- [ ] Pause/resume controls work
```

---

### Phase 6: Skills System ⏳ REQUIRES UI
**Validation:** UI Testing Required
- Skills listed in UI
- Skill parameters configurable
- Skill output formatted correctly
- Skill errors handled

```
UI Checklist:
- [ ] Skills dropdown populated
- [ ] Skill params form renders
- [ ] Skill preview displays output
- [ ] Error messages clear
```

---

### Phase 7: Brain Graph Rebuild ⏳ REQUIRES UI
**Validation:** UI Testing Required
- Brain rebuild triggered from UI
- Progress shown to user
- New notes indexed
- Search finds new content

```
UI Checklist:
- [ ] Rebuild button visible
- [ ] Progress bar shows
- [ ] Rebuild completes
- [ ] New notes searchable
```

---

### Phase 8: Production Hardening ⏳ REQUIRES UI + LOGS
**Validation:** Full integration testing
- Error handling UI display
- Recovery flows work
- Performance acceptable
- No memory leaks

```
UI Checklist:
- [ ] Error messages display
- [ ] Retry UI feedback works
- [ ] Timeouts handled gracefully
- [ ] Large deliverables render

Logs to Check:
- Memory usage stable
- No unhandled exceptions
- Recovery successful
```

---

## Validation Roadmap

### Phases 1-3: Log-Only ✅ Ready Now
```bash
# Run all validation
pytest backend/tests/ -v
# Check logs for execution flow
python -m backend.main  # Watch startup logs
```

### Phases 4-8: Require UI
Need v3.6 frontend running to validate:
- Task creation and routing
- Real-time status updates
- Result displays
- Routine management
- Brain interactions

---

## Runtime Debugging Protocol

**When platform malfunctions:**

1. **Check logs first** (backend terminal):
   ```
   [ERROR] messages indicate what failed
   [WARN] early warnings of issues
   [EXEC] execution flow tracking
   ```

2. **If debugging needed:**
   ```bash
   # Test specific phase
   pytest backend/tests/test_langgraph.py -v
   pytest backend/tests/test_execution.py -v  # Phase 3+
   
   # Test API directly
   curl http://localhost:8000/api/health
   curl -X POST http://localhost:8000/api/tasks ...
   ```

3. **LangGraph/LangChain issues:**
   - Check node output in logs
   - Verify state transitions
   - Review agent execution traces
   - Validate tool calls

---

## Phases Ready for Testing

### ✅ Phase 1-2: Ready Now (Log Validation)
- Backend fully deployed
- 34 tests passing
- All infrastructure in place
- No UI needed

### ⏳ Phase 3: Next (Log Validation)
- Add Claude API integration
- Add retry/escalation logic
- Validate through logs and tests
- No UI needed

### 🎯 Phase 4+: Requires UI
- Need v3.6 frontend cloned and integrated
- Full stack testing
- User-facing validation

---

## Current Status

| Phase | Status | UI Needed | Validation Method |
|-------|--------|-----------|-------------------|
| 1 | ✅ Complete | No | Tests (21/21) |
| 2 | ✅ Complete | No | Tests (34/34) |
| 3 | ⏳ Next | No | Tests + logs |
| 4 | 🔄 Design Ready | **YES** | UI + logs |
| 5 | 🔄 Design Ready | **YES** | UI + logs |
| 6 | 🔄 Design Ready | **YES** | UI + logs |
| 7 | 🔄 Design Ready | **YES** | UI + logs |
| 8 | 🔄 Design Ready | **YES** | UI + logs |

**Next Step:** Proceed with Phase 3 (Claude API integration, log validation). When Phase 4+ needed, integrate v3.6 frontend.
