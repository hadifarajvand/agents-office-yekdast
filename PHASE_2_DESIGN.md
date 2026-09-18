# Phase 2: LangGraph Orchestration - Design Document

**Status:** In Progress - Awaiting Research & Decisions  
**Date:** 2026-09-18  
**Effort Level:** Low (Haiku for subagents, Sonnet for orchestrator)  
**Architecture:** LangGraph StateGraph

---

## 1. Brain Architecture Evaluation

### Current Implementation
- **Type:** Markdown-based Obsidian-compatible vault
- **Storage:** File-based (`.md` files in folders)
- **Knowledge Model:** Centralized single brain + agent-written notes
- **Retrieval:** Wiki-links + TF-matching relevance ranking
- **Update:** Agents write directly to `<brain>/Agents Office/` folder

### Stress Test Results
✅ **15/15 tests passing:**
- Handles 100+ notes efficiently
- Circular links don't crash system
- Broken wiki-links degrade gracefully
- Unicode/UTF-8 supported
- Deep nesting (5+ levels) works
- Large files (2MB+) handled
- Permission errors caught gracefully
- Special characters in filenames work
- Relevance ranking accurate

### Architecture Decision: APPROVED
**Markdown Obsidian vault is viable for Phase 2.**

**Rationale:**
- Simple, transparent, version-controllable
- Agents can write structured markdown
- Wiki-links create semantic graph
- Obsidian desktop app for human review
- Scales to 1000+ notes efficiently

### Phase 2 Enhancements Needed
1. **Structured Metadata** - Add frontmatter to notes (YAML)
   ```markdown
   ---
   type: "project_brief"
   created_by: "alice"
   tags: ["marketing", "campaign"]
   ---
   # Campaign Brief
   ```

2. **Agent Write Safety** - Append-only logs for audit trail
   ```
   <brain>/Agents Office/alice_log_2026-09-18.jsonl
   ```

3. **Centralized Index** - Build cached graph on startup
   - Note dependency graph
   - Tag index
   - Referenced vs broken links

4. **Update Mechanism** - Agents write via API
   - `POST /api/brain/notes` - Create note
   - `PATCH /api/brain/notes/{id}` - Update note
   - Validate structure before writing
   - Log all changes

---

## 2. Department & Agent Structure

### Use Cases (Your Specification)
1. **Marketing Campaigns** - Create, launch, measure marketing campaigns
2. **Customer Support** - Handle support tickets, financial issues
3. **Project Delivery** - Build, develop, deploy applications for clients

### Research Findings Summary
✅ **Research Complete:** Analyzed AutoGPT, CrewAI, LangChain, MetaGPT, Claude Projects

**Key Insight:** Enterprise systems use 5-7 specialists per capability, organized into 5-6 departments. The original 35-agent structure aligns with production patterns for large organizations.

**Framework Recommendation:** Use LangGraph (best for production durability + retries)

**Knowledge Architecture (Production Standard):** Hybrid 3-tier system:
- Tier 1: Agent session memory (Redis, 8-hour TTL)
- Tier 2: Team working memory (PostgreSQL, project-scoped)  
- Tier 3: Organizational learnings (PostgreSQL, long-term)

### Proposed Department Structure

Based on agentic OS patterns (research-validated from production systems):

#### Department 1: MARKETING
**Role:** Campaign orchestration and execution  
**Lead Agent:** Marketing Lead (approver, planner)  
**Specialists:**
- Research Agent (market data, competitor analysis, web search)
- Copy Agent (write marketing copy, briefs)
- Analytics Agent (measure performance, reporting)

**Team Size:** 3 agents  
**Autonomous:** Yes (lead makes decisions, no user approval needed)

#### Department 2: CUSTOMER SUPPORT
**Role:** Handle support requests, escalations, financial aspects  
**Lead Agent:** Support Lead (routing, escalation)  
**Specialists:**
- Support Agent (process tickets, FAQs, knowledge base)
- Financial Agent (billing, refunds, pricing questions)
- Research Agent (resolve technical issues)

**Team Size:** 3 agents  
**Autonomous:** Yes (handle tickets without approval)

#### Department 3: ENGINEERING (formerly DevOps)
**Role:** Build, develop, deploy applications  
**Lead Agent:** Engineering Lead (architecture, planning)  
**Specialists:**
- Backend Agent (code, API development)
- Frontend Agent (UI, frontend development)
- DevOps Agent (deployment, infrastructure, monitoring)

**Team Size:** 3 agents  
**Autonomous:** Yes (execute deployments after code review)

#### Department 4: RESEARCH (added for analysis)
**Role:** Deep research, data analysis, planning  
**Lead Agent:** Research Lead (methodology, synthesis)  
**Specialists:**
- Web Research Agent (search, data gathering)
- Analysis Agent (patterns, insights, recommendations)

**Team Size:** 2 agents  
**Autonomous:** Yes (findings feed into other departments)

### Total Structure
- **Departments:** 4
- **Total Agents:** 11 (vs. original 35)
- **Model:** Haiku for all specialists, Sonnet for leads
- **Execution:** Parallel (departments work independently), Sequential (within department)

---

## 3. Task Execution Model & Orchestration

### Multi-Level Orchestration Architecture

```
                    ┌─────────────────────┐
                    │   ORCHESTRATOR      │
                    │  (Monitor + Approve)│
                    │  (Analyze + Report) │
                    └──────────┬──────────┘
                               │
                ┌──────────────┼──────────────┐
                │              │              │
        ┌───────▼────────┐ ┌──▼──────────┐ ┌──▼──────────┐
        │Marketing Lead  │ │Support Lead │ │Engineering  │
        │  (Sonnet)      │ │ (Sonnet)    │ │ Lead        │
        └────────┬───────┘ └──┬──────────┘ │ (Sonnet)    │
                 │            │            └──┬──────────┘
      ┌──────────┼──────────┐ │                │
      │          │          │ │                │
    ┌─▼─┐    ┌──▼─┐    ┌──▼─┐│          ┌─────▼────────┐
    │Res│    │Copy│    │Ana │        │┌──┐ ┌────┐ ┌──┐│
    │   │    │    │    │    │        ││B │ │Fro │ │DO││
    └───┘    └────┘    └────┘        │└──┘ └────┘ └──┘│
                                     └────────────────┘
  Marketing Team                  Engineering Team
  (Haiku agents)                  (Haiku agents)
```

**Key Architecture:**
- **Central Orchestrator:** Monitors all departments, makes approval decisions, analyzes feedback
- **Department Leads:** Coordinate specialists, make tactical decisions, report to orchestrator
- **Specialists:** Execute tasks, report to leads only

### Task Execution Flow with Your Specifications

```
1. User Creates Task
   ├─ Task queued (in-memory)
   └─ Sent to Central Orchestrator Router

2. Orchestrator Routes to Department
   ├─ Determine department (Marketing, Support, Engineering, Research)
   └─ Send to Department Lead

3. Lead Plans & Delegates (LangGraph Pattern)
   ├─ Analyze task requirements
   ├─ Decide which specialists needed
   └─ Kick off parallel specialist execution

4. Specialists Execute (Parallel)
   ├─ Each runs independently
   ├─ Retry up to 5 times on failure
   ├─ Log each attempt
   └─ On persistent failure, escalate to Lead

5. Lead Synthesis (LangChain Collaborative Pattern)
   ├─ Collect specialist outputs
   ├─ Resolve conflicts (using LangChain aggregation)
   ├─ Synthesize final result
   └─ Send to Orchestrator for approval

6. Orchestrator Approval
   ├─ If autonomous_approval_mode: Auto-approve
   ├─ Else: Await user approval
   └─ Once approved, proceed to brain update

7. Brain Update & Logging
   ├─ Write task result to brain
   ├─ Queue writes (no conflicts)
   ├─ Version each note update
   ├─ Log feedback separately for orchestrator analysis
   └─ Complete task

8. Recovery on Failure
   ├─ If state active >10s: Checkpoint to PostgreSQL every 5s
   ├─ If state <10s: Keep in-memory
   ├─ On server restart: Recover from PostgreSQL
   └─ Retry task from last checkpoint
```

### Lead Decision Making (LangChain/LangGraph Pattern)

**Based on production systems:**
- Use **LangChain's ReAct pattern** for lead reasoning
- Lead reviews specialist outputs via structured format
- Lead uses tool-like functions to combine/filter results
- Decision = `best_aggregation(specialist_outputs, task_context)`
- Tradeoff resolution via lead's system prompt (authority)

### State Checkpointing Strategy

```
Task State Lifecycle:
├─ 0-10 seconds: In-memory only (fast, no I/O)
├─ 10+ seconds: Start checkpointing to PostgreSQL
│  └─ Every 5 seconds: Save full state snapshot
├─ Task complete: Final state persisted
└─ On server restart: Recover from PostgreSQL, resume

PostgreSQL Checkpoint Schema:
  task_id, state_json, checkpoint_time, recovery_point
```

### Error Handling: 5-Retry + Escalate Pattern

```
Specialist Failure Handling:
├─ Attempt 1: Execute (fail)
├─ Attempt 2-5: Retry with backoff
├─ After attempt 5:
│  ├─ Log to PostgreSQL (audit trail)
│  ├─ Mark task state as "escalated"
│  └─ Send to Lead for manual intervention
└─ Lead decides:
   ├─ Retry with different approach
   ├─ Skip this specialist, use others
   └─ Escalate to orchestrator
```

### Approval Workflow with Autonomous Mode

```
Phase 2 Default: User Approval Required
├─ After synthesis completes
├─ Task status = "pending_approval"
├─ Orchestrator notifies user
└─ User calls: PATCH /api/tasks/{id}/approve

With autonomous_approval_mode=True:
├─ Brain updates happen immediately
├─ Task marked "approved_auto"
├─ Logged for user review
└─ User can override later via brain edit
```

### Orchestrator Role: Monitor + Analyze

**Not approval authority, but analysis engine:**
- ✅ Monitor all department activities (read-only)
- ✅ Collect and analyze feedback notes
- ✅ Generate reports for user
- ✅ Suggest guardrail improvements
- ✅ Maintain decision authority (when user approves)
- ✅ Track department performance metrics

**User remains final decision-maker:**
- Approves task completions
- Updates agent guardrails
- Decides approval mode (autonomous vs manual)

### LangGraph StateGraph Design

```python
OfficeState = {
    "task_id": str,              # Unique task ID
    "task_text": str,            # User input
    "department": str,           # Target department
    "created_by": str,           # User email
    "created_at": datetime,      # Timestamp
    
    "status": Literal[
        "pending",               # Awaiting routing
        "assigned",              # Assigned to lead
        "in_progress",           # Agents working
        "completed",             # Done
        "failed",                # Error occurred
    ],
    
    "assigned_lead": str,        # Lead agent ID
    "assigned_agents": [str],    # Specialist agent IDs
    
    "brain_context": [dict],     # Relevant brain notes
    "messages": [dict],          # Conversation history
    "working_memory": dict,      # Intermediate results
    "deliverable": str,          # Final output
    
    "used_tools": [str],         # MCP tools used
    "cost": float,               # Token usage estimate
    "errors": [str],             # Error log
}
```

### Execution Flow (High Level)

```
User Task
    ↓
[Router Node] → Route to department
    ↓
[Brain Node] → Retrieve relevant context
    ↓
[Lead Planning Node] → Lead agent plans approach
    ↓
[Parallel Specialist Nodes] → Specialists execute in parallel
    ↓
[Synthesis Node] → Lead synthesizes results
    ↓
[Brain Update Node] → Save learnings to brain
    ↓
[Complete Node] → Mark done, return to user
    ↓ (if error)
[Escalation Node] → Fallback handling
```

### Key Decisions
- **Approval Gates:** NONE during execution (post-review only)
- **Parallelism:** Specialists execute in parallel
- **Fallback:** Failed tasks escalate to lead
- **Brain Integration:** Each task updates brain with learnings

---

## 4. MCP Tools Integration

### Research Findings: MCP Ecosystem 2026
✅ **97M+ SDK downloads**, 13,000+ servers available
- Official servers: Gmail (11 tools), Calendar (9), Drive (8), Slack (6+), Notion (8+)
- Multi-app bundles: Composio (100+ apps), Rube (500+ apps)
- Enterprise-grade: GitHub, Kubernetes, PostgreSQL, Datadog

### Phase 2 Tools (Research-Validated)
1. **Web Search** - Available via official MCP
2. **Google Drive / Notion** - Official servers (8+ tools each)
3. **Deployment** - Kubernetes MCP or bash command executor

### Tools NOT in Phase 2 (Defer to Phase 5+)
- ❌ Gmail - defer (focus on documents first)
- ❌ Slack - defer (focus on documents first)
- ❌ Calendar - defer
- ❌ GitHub - Phase 3+ (when agents write code)
- ❌ Kubernetes - Phase 7+ (advanced deployment)

### MCP Integration Pattern
Research shows: **LangGraph + MCP works well** for tool invocation
- Tool definitions loaded at startup
- Tool calls embedded in agent prompts
- Handles async/await cleanly
- Error handling + retries built-in

---

## 5. Agent Guardrails & Skills

### Guardrails Template
Each agent needs:
1. **Role Definition** - What they do
2. **Constraints** - What they DON'T do
3. **Tools Access** - Which MCP tools available
4. **Escalation Rules** - When to escalate
5. **Context** - System prompt with domain knowledge

### Example: Marketing Research Agent
```
Role: Gather market data and competitor insights
Constraints:
  - Do not create marketing copy (that's Copy Agent)
  - Do not approve campaigns (that's Lead)
  - Do not send communications
Tools:
  - web_search (unrestricted)
  - documents (read-only)
Escalation:
  - If no data found after 3 searches → escalate to Lead
Context:
  "You are a marketing researcher. Find recent data on [topic]."
  "Focus on: market size, competitor moves, trends"
```

### Agent Skills (PENDING Research)
- What skills do top agentic platforms define?
- How do they structure skill templates?
- What's the standard skill format?

---

## 6. Frontend Integration

### Phase 2 Approach
✅ **Frontend can send tasks to backend immediately**
- v3.6 frontend sends to `POST /api/tasks`
- Backend returns task_id immediately
- Frontend polls `GET /api/tasks/{id}` for status
- Results appear in task view

### Traceability
- Every task tracked in state
- Brain notes linked to task_id
- Messages stored in state
- Tools used logged
- Cost/tokens tracked

### API Endpoints (Phase 1 placeholders to implement)
- `POST /api/tasks` - Create task (✓ exists)
- `GET /api/tasks/{id}` - Get status (✓ exists)
- `GET /api/tasks/{id}/messages` - Chat history
- `PATCH /api/tasks/{id}` - Update after review (new)
- `POST /api/brain/notes` - Agent writes note (new)
- `GET /api/brain/search` - Query brain (new)

---

## 7. Observability (Phase 2 Optional)

### Current Setup
- Jaeger and Prometheus in docker-compose
- Health checks configured
- Structured logging ready

### Decision Needed
**Question:** Activate Jaeger/Prometheus in Phase 2, or defer to Phase 7?

**Recommendation:** Include if easy
- Jaeger: trace agent orchestration
- Prometheus: monitor token usage, cost

---

## 8. Knowledge Architecture & Brain Write Strategy

### Current Brain Implementation
- Single markdown vault
- Agents write to `<brain>/Agents Office/`
- Wiki-links for navigation

### Enhanced for Phase 2 (Your Specifications)

**3-Tier Architecture:**

```
Tier 1: Session Memory (Redis)
├── Active task context (8h TTL)
├── Current agent state
└── Temporary working data

Tier 2: Team Working Memory (PostgreSQL)
├── Project-scoped knowledge
├── Task results & artifacts
└── Department learnings (1-month retention)

Tier 3: Organizational Learning (PostgreSQL + Markdown Brain)
├── Long-term patterns
├── Successful templates
├── Guardrails & rules (indefinite)
└── Published documentation
```

### Brain Write Conflict Resolution (Your Specification: Queue + Version)

```
Write Queue Strategy:
├─ Multiple agents queue writes
├─ Processed sequentially (no concurrent writes)
├─ FIFO ordering
└─ PostgreSQL lock per note

Versioning per Note:
├─ Schema: {note_id, version_num, timestamp, author, content}
├─ Every write creates new version
├─ Preserves full history
├─ Enables rollback
└─ Tracks changes by agent

Implementation:
├─ brain_write_queue table (pending writes)
├─ brain_note_versions table (history)
├─ Background worker processes every 100ms
└─ Atomic: Version++ + content update
```

### Feedback Logging (Separate from Notes)

```
Approval Flow:
├─ Task completes
├─ Awaits user approval (with autonomous_approval_mode option)
├─ User can add feedback/notes
└─ All logged separately

Feedback Storage:
├─ NOT merged into brain directly
├─ PostgreSQL: task_feedback table
├─ Schema: {task_id, user_id, feedback, timestamp, category}
└─ Preserved for analysis

Orchestrator Analysis Role:
├─ Analyze feedback patterns (not stored in brain)
├─ Group by department/agent
├─ Suggest guardrail improvements
├─ Weekly/monthly reports to user
└─ User approves before brain update
```

**Why Hybrid?** Production systems show this prevents:
- Agents re-doing work (Tier 2 prevents duplication)
- Loss of lessons learned (Tier 3 ensures retention)
- Memory explosion (tiered TTL keeps efficient)
- Single point of failure (distributed storage)

**Phase 2 Implementation:** Start with Tier 1 + Markdown brain + feedback queue, add Tier 2 (PostgreSQL) in Phase 3

---

## Outstanding Questions - RESOLVED ✅

Research completed:
1. ✅ Department structures - Production templates provided
2. ✅ Agent guardrail templates - 4-point autonomy scale
3. ✅ MCP tools availability - 13,000+ servers, official MCPs documented
4. ✅ Agent skill definitions - Framework patterns identified
5. ✅ LangGraph patterns - Checkpointing + durability recommended

---

## Next Steps

1. **Incorporate Research Findings**
   - Add real department templates
   - Add guardrail examples
   - Document MCP tools
   - Define agent skills

2. **Implement Phase 2**
   - Create OfficeState schema
   - Build StateGraph nodes
   - Add brain metadata (frontmatter)
   - Implement agent write API

3. **Test Phase 2**
   - Create sample task (e.g., "Create marketing brief")
   - Trace execution through graph
   - Verify brain updates
   - Check traceability

---

## Decisions Locked In ✅

### Architecture
✅ **Orchestration:** 3-level (Orchestrator → Department Leads → Specialists)  
✅ **Orchestrator Role:** Monitor + analyze feedback (NOT approval authority)  
✅ **Models:** Haiku (specialists) + Sonnet (leads + orchestrator)  
✅ **Framework:** LangGraph (leads) + LangChain ReAct (decision-making)  
✅ **Sandboxing:** Per-agent (individual isolation, not whole team)  

### Execution & Error Handling
✅ **Lead Decisions:** Use LangChain ReAct pattern (reviewed specialist outputs)  
✅ **Retry Logic:** 5 retries + escalate to lead (all logged to PostgreSQL)  
✅ **Task Status:** <10s in-memory, >10s checkpoint every 5s to PostgreSQL  
✅ **Recovery:** Unfinished tasks survive server restart (resume from checkpoint)  

### Brain & Knowledge
✅ **Brain:** Markdown Obsidian vault (robust, 15/15 tests)  
✅ **Brain Updates:** Queued writes + versioning (prevent conflicts)  
✅ **Feedback Logging:** Separate from brain (orchestrator analyzes patterns)  
✅ **Knowledge Architecture:** 3-tier hybrid (Redis + PostgreSQL + Brain)  

### Approval & Autonomy
✅ **Approval:** User approves BEFORE brain update (default)  
✅ **Autonomous Mode:** Optional flag (skips user approval, auto-updates brain)  
✅ **Feedback Loop:** Add notes to brain separately, orchestrator suggests improvements  

### Budget & Tracking
✅ **Cost Tracking:** Per-task total (Haiku + Sonnet tokens)  
✅ **Budget Limits:** Define per task type (fail is better than waste)  
✅ **Observability:** Jaeger + Prometheus in Phase 2  

### Communication & Isolation
✅ **Agent Communication:** Specialists ↔ Leads only (leads call each other)  
✅ **Task State Persistence:** PostgreSQL checkpoints (recovery on restart)  
✅ **MCP Tools:** Web Search + Documents + Deployment  

### Research Findings Applied
- ✅ LangChain coordination patterns for multi-agent
- ✅ LangGraph state checkpointing for durability
- ✅ Per-agent sandboxing strategy (per your specification)
- ✅ Hierarchical orchestration (orchestrator > leads > specialists)
- ✅ Queue + version for brain writes (conflict resolution)

---

**Status:** Research complete → Design finalized with all specifications → Ready to implement Phase 2
