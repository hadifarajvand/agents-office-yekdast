# Phase 2 Implementation Checklist

**Status:** Ready to implement  
**Duration:** ~5 days  
**Framework:** LangGraph + LangChain + FastAPI  
**Research:** Pending (LangChain/LangGraph patterns)

---

## Core Architecture Components

### 1. State & Schemas (Day 1)
- [ ] **OfficeState schema**
  - [ ] task_id, task_text, department, created_by, created_at
  - [ ] status: pending → assigned → in_progress → completed/failed
  - [ ] assigned_lead, assigned_agents (list)
  - [ ] brain_context, messages, working_memory, deliverable
  - [ ] used_tools, cost (tokens), errors
  - [ ] State version for checkpointing

- [ ] **Lead/Specialist state types** (for hierarchical execution)

- [ ] **Brain metadata schema** (YAML frontmatter)
  - [ ] type: project, brief, learning, template
  - [ ] created_by, created_at, tags
  - [ ] department, related_tasks, status, version

- [ ] **PostgreSQL checkpoint schema**
  - [ ] task_id, state_json, checkpoint_time, recovery_point, version

- [ ] **Feedback schema** (separate from brain)
  - [ ] task_id, user_id, feedback_text, timestamp, category
  - [ ] NOT merged into brain directly

### 2. LangGraph StateGraph (Day 1-2)
- [ ] **Router Node**
  - [ ] Input: task
  - [ ] Output: route to department
  - [ ] Uses department mapping

- [ ] **Brain Context Node**
  - [ ] Input: task + department
  - [ ] Output: retrieve relevant notes (rank_by_relevance)
  - [ ] Cache results in state

- [ ] **Lead Planning Node** (uses LangChain ReAct)
  - [ ] Input: task + brain_context
  - [ ] Output: plan (which specialists, approach)
  - [ ] Model: Sonnet (lead)

- [ ] **Specialist Nodes** (parallel execution)
  - [ ] Input: subtask, context
  - [ ] Output: result
  - [ ] Model: Haiku
  - [ ] Include retry logic (5 attempts max)
  - [ ] Escalate to lead on failure

- [ ] **Synthesis Node** (LangChain aggregation)
  - [ ] Input: specialist outputs
  - [ ] Combine/filter/resolve conflicts
  - [ ] Output: final deliverable
  - [ ] Model: Sonnet (lead)

- [ ] **Brain Update Node**
  - [ ] Queue write (no concurrent updates)
  - [ ] Create new version
  - [ ] Persist to PostgreSQL

- [ ] **Approval Node**
  - [ ] If autonomous_approval_mode: auto-approve
  - [ ] Else: await user approval (API call)

- [ ] **Complete Node**
  - [ ] Mark task completed
  - [ ] Log to PostgreSQL
  - [ ] Return to user

### 3. Orchestration & Department Leads (Day 2)
- [ ] **Central Orchestrator**
  - [ ] Monitor all departments
  - [ ] Route tasks to department leads
  - [ ] Approve/reject (with autonomous mode option)
  - [ ] Analyze feedback patterns (separate)
  - [ ] Generate reports

- [ ] **Department Lead Agents** (4 departments)
  - [ ] Marketing Lead (Sonnet)
  - [ ] Support Lead (Sonnet)
  - [ ] Engineering Lead (Sonnet)
  - [ ] Research Lead (Sonnet)

- [ ] **Specialist Agents** (11 total, Haiku)
  - [ ] Marketing: Research, Copy, Analytics
  - [ ] Support: Support, Financial, Research
  - [ ] Engineering: Backend, Frontend, DevOps
  - [ ] Research: Web Researcher, Analyst

- [ ] **System Prompts** (based on LangChain/LangGraph templates)
  - [ ] Lead prompt: decision-making authority
  - [ ] Specialist prompts: narrow focus, defined role
  - [ ] Escalation triggers per specialist

### 4. Error Handling & Retries (Day 2)
- [ ] **Retry Logic**
  - [ ] Attempt 1-5: Retry with backoff
  - [ ] All attempts logged to PostgreSQL (audit trail)
  - [ ] After 5 failures: escalate to lead
  - [ ] Lead chooses: retry different approach or skip

- [ ] **Escalation Handler**
  - [ ] Log failure reason
  - [ ] Notify lead agent
  - [ ] Update task state to "escalated"
  - [ ] Wait for lead decision

### 5. State Persistence & Checkpointing (Day 2-3)
- [ ] **In-Memory State** (<10 seconds)
  - [ ] Keep in Redis (fast)
  - [ ] No persistence to PostgreSQL

- [ ] **Checkpoint Trigger** (>10 seconds)
  - [ ] Start checkpointing
  - [ ] Every 5 seconds: save full state to PostgreSQL
  - [ ] Include version + recovery_point

- [ ] **Recovery on Restart**
  - [ ] Load tasks from PostgreSQL where status != "completed"
  - [ ] Resume from last checkpoint
  - [ ] Retry unfinished work
  - [ ] Clean up stale sessions

### 6. Brain Write System (Day 3)
- [ ] **Write Queue**
  - [ ] PostgreSQL: brain_write_queue table
  - [ ] Queue concurrent writes
  - [ ] Process sequentially (FIFO)
  - [ ] Lock per note during write

- [ ] **Versioning**
  - [ ] PostgreSQL: brain_note_versions table
  - [ ] Track version_num, timestamp, author, content
  - [ ] Preserve history
  - [ ] Enable rollback

- [ ] **Background Worker**
  - [ ] Process queue every 100ms
  - [ ] Atomic: Version increment + update
  - [ ] Release lock
  - [ ] Log completion

### 7. Approval Workflow (Day 3)
- [ ] **User Approval (Default)**
  - [ ] Task synthesis complete → pending_approval
  - [ ] Notify user via API
  - [ ] User calls: PATCH /api/tasks/{id}/approve
  - [ ] On approval: proceed to brain update

- [ ] **Autonomous Approval Mode**
  - [ ] Optional flag: autonomous_approval_mode = true
  - [ ] Brain updates happen immediately
  - [ ] Task marked: approved_auto
  - [ ] Logged for user review

### 8. Feedback Loop & Analysis (Day 3-4)
- [ ] **Feedback Collection**
  - [ ] After task (success or failure)
  - [ ] User can add notes (optional)
  - [ ] Store separately in PostgreSQL
  - [ ] Schema: task_feedback table

- [ ] **Feedback Analysis** (Orchestrator job)
  - [ ] Group by department/agent
  - [ ] Identify patterns
  - [ ] Suggest guardrail improvements
  - [ ] Weekly/monthly reports to user

- [ ] **Brain Update from Feedback**
  - [ ] User approves improvement
  - [ ] Only then: write to brain
  - [ ] Preserves brain quality (no noise)

### 9. Cost Tracking (Day 4)
- [ ] **Per-Task Cost**
  - [ ] Track Haiku tokens (specialists)
  - [ ] Track Sonnet tokens (leads)
  - [ ] Sum to total_cost
  - [ ] Store in task state

- [ ] **Budget Limits**
  - [ ] Define per task type (optional)
  - [ ] Warning at 80% budget
  - [ ] But DON'T stop execution (fail is better than waste)

### 10. Agent Communication (Day 4)
- [ ] **Specialist ↔ Lead**
  - [ ] Message via state
  - [ ] Only their own lead
  - [ ] No direct specialist-to-specialist

- [ ] **Lead ↔ Lead**
  - [ ] Cross-department requests
  - [ ] Via orchestrator coordination
  - [ ] Example: Engineering lead needs marketing research

### 11. API Endpoints (Day 4)
- [ ] **Task API (Enhance existing)**
  - [ ] POST /api/tasks - create task
  - [ ] GET /api/tasks/{id} - get status
  - [ ] PATCH /api/tasks/{id} - update status
  - [ ] PATCH /api/tasks/{id}/approve - approve with feedback
  - [ ] GET /api/tasks - list tasks (filter by status, dept)

- [ ] **Brain API (New)**
  - [ ] POST /api/brain/notes - agents create note
  - [ ] PATCH /api/brain/notes/{id} - agents update note
  - [ ] GET /api/brain/search - query by relevance
  - [ ] GET /api/brain/notes/{id} - get single note

- [ ] **Trace & Monitoring (New)**
  - [ ] GET /api/tasks/{id}/trace - full execution trace
  - [ ] GET /api/tasks/{id}/messages - message history
  - [ ] GET /api/metrics - cost/token usage

- [ ] **Approval API (New)**
  - [ ] GET /api/pending-approvals - list pending user approval
  - [ ] POST /api/tasks/{id}/feedback - add user feedback

### 12. Per-Agent Sandboxing (Day 5)
- [ ] **Research LangChain/LangGraph patterns** for:
  - [ ] Tool isolation per agent
  - [ ] Permission model
  - [ ] Resource limits
  - [ ] Docker container patterns

- [ ] **Sandbox Implementation**
  - [ ] Each agent loads only allowed MCP tools
  - [ ] Resource limits (timeout, max tokens)
  - [ ] Audit logging per agent call
  - [ ] Phase 7: Container isolation

### 13. Testing (Day 5)
- [ ] **Unit Tests**
  - [ ] OfficeState schema validation
  - [ ] Each node (router, brain, lead, synthesis, etc.)
  - [ ] Error handling & retries
  - [ ] State checkpointing

- [ ] **Integration Tests**
  - [ ] Full task execution flow
  - [ ] Multi-specialist coordination
  - [ ] Brain write (queue + version)
  - [ ] Approval workflow
  - [ ] Recovery on restart

- [ ] **End-to-End Tests**
  - [ ] Create task (user)
  - [ ] Execute through departments
  - [ ] Get approval
  - [ ] Verify brain updates
  - [ ] Check cost tracking

---

## Dependencies & Decisions Pending

### Waiting For:
- [ ] LangChain/LangGraph multi-agent patterns research
  - [ ] How to implement lead decision-making
  - [ ] How to coordinate specialists
  - [ ] System prompt templates
  - [ ] Tool isolation per agent

### Research Deliverables Needed:
- [ ] LangChain ReAct pattern example (for lead decisions)
- [ ] LangGraph multi-agent state management
- [ ] Per-agent tool/permission isolation
- [ ] Sandbox/container patterns

---

## Files to Create/Modify

### New Files
- [ ] `backend/langgraph/__init__.py`
- [ ] `backend/langgraph/state.py` - State schemas
- [ ] `backend/langgraph/nodes.py` - All node implementations
- [ ] `backend/langgraph/graphs.py` - StateGraph + department graphs
- [ ] `backend/langgraph/agents.py` - Agent definitions (prompts, tools)
- [ ] `backend/mcp/tools.py` - MCP tool wrappers
- [ ] `backend/services/checkpoint.py` - PostgreSQL checkpointing
- [ ] `backend/services/orchestrator.py` - Orchestrator logic
- [ ] `backend/api/approval.py` - Approval endpoints
- [ ] `backend/tests/test_langgraph.py` - Graph tests
- [ ] `backend/tests/test_orchestration.py` - Orchestration tests

### Modify Files
- [ ] `backend/main.py` - Add new endpoints
- [ ] `backend/config.py` - Add orchestrator config
- [ ] `backend/services/brain.py` - Add versioning + queue
- [ ] `requirements.txt` - Ensure langgraph, langchain latest

---

## Go/No-Go Criteria

### Ready to Start Phase 2 When:
- [ ] All decisions locked in (✅ Done)
- [ ] LangChain/LangGraph research complete (🔄 In progress)
- [ ] PHASE_2_DESIGN.md comprehensive (✅ Done)
- [ ] Git repo clean (✅ Done)
- [ ] Team aligned on architecture (✅ Done)

### Phase 2 Success Criteria:
- [ ] All 21 existing tests still pass
- [ ] 50+ new tests added (LangGraph, orchestration)
- [ ] Single task execution end-to-end working
- [ ] Brain updates working (queue + version)
- [ ] State checkpointing working
- [ ] Approval workflow working (user + autonomous modes)

---

## Timeline (Estimated)

| Day | Component | Status |
|-----|-----------|--------|
| 1 | State schemas + LangGraph nodes | Pending |
| 2 | StateGraph + orchestration | Pending |
| 2-3 | Error handling + checkpointing | Pending |
| 3 | Brain write system + approval | Pending |
| 4 | Cost tracking + API endpoints | Pending |
| 5 | Testing + documentation | Pending |

**Actual start:** Pending research completion

---

## Questions Resolved ✅

✅ Agent system prompts → Use LangChain/LangGraph templates  
✅ Lead decisions → LangChain ReAct pattern  
✅ Retry logic → 5 attempts + escalate  
✅ Brain conflicts → Queue + Version  
✅ State persistence → <10s in-memory, >10s checkpoint  
✅ Approval → User (default) + autonomous mode  
✅ Feedback → Separate storage, orchestrator analyzes  
✅ Agent communication → Specialists to leads, leads to each other  
✅ Sandboxing → Per-agent (research templates needed)  

---

**Awaiting:** LangChain/LangGraph research → Ready to implement Phase 2
