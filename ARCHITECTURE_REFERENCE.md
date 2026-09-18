# Multi-Agent Architecture Reference for Phase 2

**Status:** Quick Reference & Decision Guide  
**Date:** 2026-09-18  
**Audience:** Phase 2 Implementation Team

---

## 1. Architecture Comparison

### LangChain vs LangGraph

| Aspect | LangChain | LangGraph | Agent Office Choice |
|--------|-----------|-----------|-------------------|
| **Framework Type** | Agent library + chains | Graph orchestration | **LangGraph** |
| **State Management** | Implicit (message history) | Explicit (TypedDict) | **LangGraph** |
| **Durability** | Stateless agents | Checkpointable state | **LangGraph** |
| **Error Recovery** | Manual retry loops | Built-in checkpoint restore | **LangGraph** |
| **Parallelism** | Sequential by default | Native parallel nodes | **LangGraph** |
| **Production Readiness** | Good for simple tasks | Enterprise-grade | **LangGraph** |
| **Learning Curve** | Gentle | Moderate | Accept cost |

**Decision Rationale:** LangGraph's explicit state management + checkpointing enables the robustness and recovery needed for autonomous multi-agent systems.

---

## 2. Execution Flow Diagram

```
Phase 2 Task Execution Flow
═══════════════════════════════════════════════════════════════

User Input
    │
    ├─ task_id: "task_001"
    ├─ task_text: "Create Q3 marketing brief"
    └─ department: "" (auto-detected)
    ↓
    
┌─────────────────────────────────────────────────────────────┐
│ START NODE                                                  │
│ - Create OfficeState                                        │
│ - Save checkpoint #1                                        │
└─────────────────────────────────────────────────────────────┘
    ↓
    
┌─────────────────────────────────────────────────────────────┐
│ ROUTER NODE (Haiku inference: 100ms)                        │
│ - Classify task: "Create Q3..." → "marketing"              │
│ - Assign department = "marketing"                           │
│ - Save checkpoint #2                                        │
│ Status: "assigned"                                          │
└─────────────────────────────────────────────────────────────┘
    ↓
    
┌─────────────────────────────────────────────────────────────┐
│ BRAIN CONTEXT NODE (DB query: 50ms)                         │
│ - Search brain: "Q3 marketing"                              │
│ - Retrieve 5 relevant notes                                 │
│ - Load into state.brain_context                            │
│ - Save checkpoint #3                                        │
└─────────────────────────────────────────────────────────────┘
    ↓
    
┌─────────────────────────────────────────────────────────────┐
│ LEAD PLANNING NODE (Sonnet: 2s)                             │
│ - Marketing Lead reads task + context                       │
│ - Plans approach (research → writing → analysis)            │
│ - Assigns specialists                                       │
│ - Status: "working"                                         │
│ - Save checkpoint #4                                        │
└─────────────────────────────────────────────────────────────┘
    ↓
    
┌──────────────────────┬──────────────────────┬──────────────────────┐
│ RESEARCH SPECIALIST  │ WRITING SPECIALIST   │ ANALYSIS SPECIALIST  │
│ (Haiku: 3s)          │ (Haiku: 2s)          │ (Haiku: 2s)          │
│                      │                      │                      │
│ - Find Q3 trends     │ - Draft copy         │ - Calculate ROI      │
│ - Competitor moves   │ - CTA messaging      │ - Risk analysis      │
│ - Market size        │ - Brand voice        │ - Market projections │
│                      │                      │                      │
│ Save checkpoint #5   │ Save checkpoint #6   │ Save checkpoint #7   │
│ [PARALLEL EXECUTION: ~3 seconds total]                             │
└──────────────────────┴──────────────────────┴──────────────────────┘
    ↓
    
┌─────────────────────────────────────────────────────────────┐
│ SYNTHESIS NODE (Sonnet: 2s)                                 │
│ - Lead reviews all specialist outputs                       │
│ - Combines into final deliverable                           │
│ - Creates cohesive campaign brief                           │
│ - Save checkpoint #8                                        │
└─────────────────────────────────────────────────────────────┘
    ↓
    
┌─────────────────────────────────────────────────────────────┐
│ BRAIN UPDATE NODE (DB write: 100ms)                         │
│ - Save deliverable to brain                                 │
│ - Create markdown note with metadata                        │
│ - Link to task_id                                           │
│ - Save checkpoint #9                                        │
└─────────────────────────────────────────────────────────────┘
    ↓
    
┌─────────────────────────────────────────────────────────────┐
│ COMPLETE NODE                                               │
│ - Status: "completed"                                       │
│ - Save checkpoint #10                                       │
│ - Total time: ~10 seconds                                   │
└─────────────────────────────────────────────────────────────┘
    ↓
    
Response to User
    │
    ├─ task_id: "task_001"
    ├─ status: "completed"
    ├─ deliverable: "[campaign brief markdown]"
    └─ brain_link: "/brain/campaign_brief_2026_09_18.md"

[Checkpoints saved to PostgreSQL: 10 total]
[Recovery possible from any checkpoint]
```

---

## 3. Hierarchical Agent Pattern

```
Department Level Orchestration
════════════════════════════════════════════════

              Task Input
                  │
                  ↓
         ┌────────────────────┐
         │  Lead Agent        │  ← Sonnet (strategic)
         │  (Marketing Lead)  │
         │                    │
         │ Responsibilities:  │
         │ • Understand goal  │
         │ • Plan approach    │
         │ • Assign work      │
         │ • Synthesize       │
         │ • Make decisions   │
         └────────┬───────────┘
                  │
      ┌───────────┼───────────┐
      │           │           │
      ↓           ↓           ↓
    
┌─────────────┐ ┌──────────────┐ ┌──────────────┐
│ Research    │ │ Writing      │ │ Analysis     │
│ Specialist  │ │ Specialist   │ │ Specialist   │
│             │ │              │ │              │
│ Haiku model │ │ Haiku model  │ │ Haiku model  │
│             │ │              │ │              │
│ • Data      │ │ • Copy       │ │ • Metrics    │
│ • Trends    │ │ • Briefs     │ │ • ROI        │
│ • Research  │ │ • Messaging  │ │ • Risks      │
└────┬────────┘ └──────┬───────┘ └──────┬───────┘
     │                 │                │
     └─────────────────┼────────────────┘
                       │
                       ↓ (Results)
         ┌────────────────────┐
         │  Lead Synthesis    │
         │  (Sonnet)          │
         │                    │
         │ • Combine results  │
         │ • Resolve conflicts│
         │ • Create final     │
         │   deliverable      │
         └────────┬───────────┘
                  │
                  ↓
            Final Output
```

### Why This Pattern Works

1. **Specialization**: Each agent focuses on one thing
2. **Scalability**: Can add more specialists without lead overhead
3. **Quality**: Lead ensures coherence and quality
4. **Explainability**: Clear who did what (audit trail)
5. **Production-proven**: Used by AutoGPT, CrewAI, MetaGPT

---

## 4. State Management Strategy

```
OfficeState TypedDict
════════════════════════════════════════════════════════════════

Immutable Reference (Set once)
├─ task_id: str              ← For tracking & checkpointing
├─ task_text: str            ← Original request
├─ created_by: str           ← User email for audit
├─ created_at: datetime      ← Timestamp
└─ department: str           ← Determined by router

Mutable Execution (Updated each node)
├─ status: str               ← pending → assigned → working → completed
├─ assigned_lead: str        ← Lead agent ID
├─ assigned_agents: list     ← Specialist IDs
└─ working_memory: dict      ← Intermediate results
    ├─ lead_plan: str        ← Lead's strategy
    ├─ research: str         ← Research findings
    ├─ writing: str          ← Draft copy
    └─ analysis: str         ← Metrics & insights

Context (Read-only during execution)
├─ brain_context: list       ← Relevant notes from brain
└─ messages: list            ← Conversation history

Output (Generated by execution)
├─ deliverable: str          ← Final output
├─ used_tools: list          ← MCP tools invoked
├─ costs: dict               ← Token usage
│   ├─ haiku: int
│   └─ sonnet: int
└─ errors: list              ← Error log


Checkpoint Timing
════════════════════════════════════════════════════════════════

Critical Nodes (Always checkpoint):
├─ START              → Initial state
├─ lead_planning      → Plan influences all specialists
├─ synthesis          → Combines all work
├─ brain_update       → Persistent storage
└─ COMPLETE           → Final state

Optional (Saves storage):
├─ router             → Fast, idempotent
├─ brain_context      → Data from DB
└─ specialists        → Can re-run if needed
```

---

## 5. Sandboxing & Permission Model

```
Tool Access Control
════════════════════════════════════════════════════════════════

Marketing Department
├─ web_search          ← Yes (need competitor data)
├─ file_read           ← Yes (past briefs)
├─ file_write          ← Yes (save briefs)
├─ google_drive        ← Yes (shared docs)
├─ database_write      ← No (prevent accidental changes)
└─ email_send          ← No (avoid spam)

Support Department
├─ knowledge_base      ← Yes (FAQ)
├─ customer_data_read  ← Yes (context)
├─ ticket_write        ← Yes (updates)
├─ email_send          ← Yes (respond to customers)
├─ payment_process     ← No (financial controls)
└─ database_write      ← No (data integrity)

Engineering Department
├─ github_read         ← Yes (view code)
├─ github_write        ← Yes (commit)
├─ database_read       ← Yes (query only)
├─ docker_build        ← Yes (build images)
├─ kubernetes_write    ← No (Phase 5: needs approval)
└─ database_schema_change ← No (permanent)

Access Control Enforcement
════════════════════════════════════════════════════════════════

      Model invokes tool
              │
              ↓
      ┌───────────────────┐
      │ Permission Check  │
      │ • Agent dept?     │
      │ • Tool allowed?   │
      │ • Action ok?      │
      └────┬──────────┬───┘
           │          │
        ✓ Allow    ✗ Deny
           │          │
           ↓          ↓
       Execute    Log error
       + Log      + Notify lead
       + Track    + Escalate
```

---

## 6. Checkpointing Strategy

```
Checkpoint Storage (PostgreSQL)
════════════════════════════════════════════════════════════════

                    Task Execution
                         │
                    ┌────┴────┐
           ┌────────┘         └────────┐
           │                           │
    Node Completes            Node Completes
           │                           │
      ┌────▼────┐              ┌──────▼────┐
      │ Is it   │              │ Is it     │
      │critical?│              │critical?  │
      └────┬──┬─┘              └──┬────┬───┘
        Yes│ │No                Yes│    │No
           │ │                     │    │
           │ ↓                     │    ↓
           │Skip (Optional)        │   Skip
           │                       ↓
        ┌──▼────────────────────────┐
        │  Save to PostgreSQL       │
        │  checkpoint TABLE         │
        │                           │
        │  (task_id, node_name,    │
        │   state_json, status)    │
        └───────────┬──────────────┘
                    │
            ┌───────▼─────────┐
            │ Task completes? │
            └───┬─────────┬───┘
            Yes │         │ No
                │         │
                ↓         ├──▼────────────────┐
            ┌──────┐      │ Task fails later  │
            │Delete│      │ Recover from      │
            │checks│      │ checkpoint #N     │
            │(opt) │      │ Resume execution  │
            └──────┘      │ at node N+1       │
                          └───────────────────┘

Checkpoint Efficiency
════════════════════════════════════════════════════════════════

Scenario 1: Happy Path (No Failures)
- 4 critical checkpoints saved
- 10KB per checkpoint = 40KB total
- Deleted on success (optional)
- Query time: <5ms

Scenario 2: Network Timeout at Node 6
- 6 checkpoints already saved
- Load checkpoint #5 (synthesis)
- Resume from brain_update
- No re-execution of specialists
- Time savings: ~3 seconds

Scenario 3: Agent Crash
- Process dies mid-execution
- Restart daemon
- Load last checkpoint
- Resume from next node
- User transparency: "Resuming from checkpoint"
```

---

## 7. Error Handling & Escalation

```
Error Handling Flow
════════════════════════════════════════════════════════════════

Agent executes node
       │
       ↓
  ┌────────────┐
  │ Success?   │
  └──┬──────┬──┘
    Yes│    │No
       │    ↓
       │  ┌──────────────────┐
       │  │ Retry Strategy?  │
       │  └────┬────────┬────┘
       │    Yes│        │No
       │       ↓        ↓
       │  ┌────────┐  ┌──────────────┐
       │  │Exponential
       │  │backoff  │  │Escalate to  │
       │  │(2s,4s  │  │department   │
       │  │8s max) │  │lead         │
       │  └────┬───┘  └────┬────────┘
       │       │           │
       │       ↓           ↓
       │    Retry      ┌──────────────┐
       │    (max 3x)   │Lead reviews  │
       │       │       │• Error msg   │
       │       │       │• Context     │
       │       │       │• Options:    │
       │       │       │  - Retry     │
       │       │       │  - Skip      │
       │       │       │  - Escalate  │
       │       │       └────┬────────┘
       │       │            │
       │       └────┬───────┘
       │            │
       └────┬───────┘
            ↓
       Continue
       execution

Autonomy Levels (4-Point Scale)
════════════════════════════════════════════════════════════════

Level 1: AUTONOMOUS
├─ When: Data gathering, analysis, drafting
├─ Execution: Immediate, no approval
├─ Logging: Full audit trail
├─ Example: Research agent web search
└─ Phase 2: ✓ All agents start here

Level 2: IN-FORM
├─ When: Routine changes logged for review
├─ Execution: Immediate, logged
├─ Review: Post-execution human review
├─ Example: Code commits
└─ Phase 2: ✓ Engineering agents

Level 3: APPROVE_FIRST
├─ When: High-impact changes
├─ Execution: Paused, waits for approval
├─ Review: Pre-execution human decision
├─ Example: Production deployments
└─ Phase 2: ⏸ Phase 5+ (conditional approval)

Level 4: HARD_STOP
├─ When: Irreversible or critical
├─ Execution: Blocked, always requires approval
├─ Review: Special authorization needed
├─ Example: Database schema changes
└─ Phase 2: ⏸ Phase 7+ (advanced sandboxing)
```

---

## 8. Token Usage & Cost Tracking

```
Token Budget for Typical Task
════════════════════════════════════════════════════════════════

Task: "Create Q3 marketing brief"

Router Node:
├─ Input: ~50 tokens (task + context)
├─ Output: ~10 tokens (dept name)
└─ Model: Haiku (cheapest)

Brain Context:
├─ Input: ~5 tokens (search query)
├─ Output: ~500 tokens (5 notes)
└─ Model: Database (free)

Lead Planning:
├─ Input: ~300 tokens (task + context)
├─ Output: ~300 tokens (strategy)
└─ Model: Sonnet (~10x more expensive)

Specialists (parallel):
├─ Research: 200 input + 400 output
├─ Writing: 200 input + 300 output
├─ Analysis: 200 input + 300 output
└─ Model: Haiku (3 agents)

Synthesis:
├─ Input: ~400 tokens (all specialist outputs)
├─ Output: ~500 tokens (final brief)
└─ Model: Sonnet

Brain Update:
├─ Input: ~100 tokens (note metadata)
├─ Output: ~10 tokens (confirmation)
└─ Model: Database (free)

Total Per Task:
├─ Haiku: ~1,500 tokens (~$0.02)
├─ Sonnet: ~1,100 tokens (~$0.10)
├─ Cost per task: ~$0.12
├─ Tasks per dollar: ~8 tasks
└─ Daily budget (1000 tasks): ~$120

Optimization Strategies:
├─ Haiku first (cheaper routing)
├─ Cache context in working_memory
├─ Parallel execution (faster = fewer retries)
└─ Reuse brain notes (avoid re-searching)
```

---

## 9. Production Deployment Checklist

### Pre-Launch (Phase 2)

```
Infrastructure
├─ [✓] PostgreSQL running (connection string set)
├─ [✓] LangGraph installed & tested
├─ [✓] FastAPI server starting
├─ [✓] Brain vault accessible
├─ [✓] Roster loaded correctly

Code
├─ [✓] OfficeState schema complete
├─ [✓] All 9+ nodes implemented
├─ [✓] StateGraph compiles
├─ [✓] Error handling in place
├─ [✓] Logging structured (JSON format)

Testing
├─ [✓] Each node tested individually
├─ [✓] State validation passes
├─ [✓] Checkpoint save/load works
├─ [✓] End-to-end workflow runs
├─ [✓] Permissions enforced
├─ [✓] Brain integration works

Documentation
├─ [✓] System prompts for each agent
├─ [✓] Permission matrix defined
├─ [✓] Deployment guide written
├─ [✓] Troubleshooting guide ready
└─ [✓] API documentation complete
```

### Launch Monitoring (First Week)

```
Metrics to Watch
├─ Task success rate (target: >95%)
├─ Average execution time (target: <15s)
├─ Error rate by department
├─ Checkpoint save failures
├─ Token usage trending
├─ Cost per task
└─ Brain growth rate

Alert Thresholds
├─ Success rate < 90% → Investigate
├─ Execution time > 30s → Log + analyze
├─ Checkpoint failures → Critical alert
├─ Token costs > 10x normal → Check for loops
└─ Errors > 100/day → Page on-call

Logs to Monitor
├─ Router decisions (classify correctly?)
├─ Lead planning outputs (coherent?)
├─ Specialist tool calls (permissions ok?)
├─ Synthesis quality (coherence?)
├─ Brain saves (write errors?)
└─ Checkpoint storage (disk growth?)
```

---

## 10. Comparison: LangChain vs LangGraph vs CrewAI

| Feature | LangChain | LangGraph | CrewAI | Agent Office |
|---------|-----------|-----------|--------|--------------|
| **State Management** | Implicit | Explicit | Implicit | LangGraph |
| **Checkpointing** | Manual | Built-in | Manual | Built-in |
| **Error Recovery** | Retry loops | Checkpoint restore | Retry only | Checkpoint + Retry |
| **Parallel Agents** | Limited | Native | Good | Native |
| **Tool Isolation** | Not built-in | Not built-in | Task-scoped | Custom matrix |
| **Learning Curve** | Gentle | Moderate | Gentle | Moderate |
| **Production Ready** | Yes (simple) | Yes (complex) | Yes | Yes |
| **Cost Control** | Manual tracking | Manual tracking | Implicit | Explicit tracking |

**Verdict for Agent Office:**
- LangGraph provides the robustness and durability needed
- Add custom permission matrix on top
- Add explicit cost tracking
- Result: Production-grade multi-agent system

---

## 11. Quick Reference: Common Patterns

### Pattern: Add New Specialist

```python
# 1. Create node function
async def specialist_new_role_node(self, state: OfficeState) -> OfficeState:
    prompt = f"You are a new_role specialist..."
    response = await self.models["haiku"].ainvoke(prompt)
    state["working_memory"]["new_role"] = response.content
    return state

# 2. Add to graph
builder.add_node("specialist_new_role", self.nodes.specialist_new_role_node)
builder.add_edge("lead_planning", "specialist_new_role")
builder.add_edge("specialist_new_role", "synthesis")

# 3. Add to system prompt registry
SYSTEM_PROMPTS["dept_new_role"] = "You are a new_role specialist..."
```

### Pattern: Add New Department

```python
# 1. Add to permission matrix
DEPT_PERMISSIONS["new_dept"] = {
    ("tool_a", "read"),
    ("tool_b", "write"),
}

# 2. Add to roster
roster.add_department({
    "name": "new_dept",
    "lead": {"id": "lead_1", "model": "sonnet"},
    "specialists": [
        {"id": "spec_1", "model": "haiku"},
    ]
})

# 3. Conditional edge in router
builder.add_conditional_edges(
    "router",
    self.route_by_department,
    {"new_dept": "brain_context", ...}
)
```

### Pattern: Add Retry Logic

```python
# Wrap node in retry loop
async def specialist_with_retry(self, state, max_retries=3):
    for attempt in range(max_retries):
        try:
            return await self.specialist_node(state)
        except Exception as e:
            if attempt == max_retries - 1:
                raise
            await asyncio.sleep(2 ** attempt)  # Exponential backoff
```

---

## 12. Reading Order

**For Implementation Team:**
1. Start here (this document)
2. Read: IMPLEMENTATION_GUIDE.md
3. Reference: MULTI_AGENT_RESEARCH.md
4. Read: PHASE_2_DESIGN.md

**For Architects:**
1. PHASE_2_DESIGN.md (requirements)
2. This document (architecture)
3. MULTI_AGENT_RESEARCH.md (deep dive)

**For Operators:**
1. IMPLEMENTATION_GUIDE.md (deployment)
2. This section (monitoring)
3. PHASE_2_DESIGN.md (context)

---

## Glossary

- **StateGraph**: LangGraph's directed acyclic graph of nodes
- **Checkpoint**: Saved state at a point in execution
- **Node**: A function that processes state
- **State**: The OfficeState TypedDict flowing through nodes
- **Lead**: Orchestrator agent (strategic, Sonnet)
- **Specialist**: Executor agent (tactical, Haiku)
- **Autonomy**: How much approval an agent needs
- **Permission**: Which tools an agent can use
- **Escalation**: Route to higher authority on failure
- **Deliverable**: Final output of task execution
- **Brain**: Knowledge base (markdown vault + DB)

---

**Next:** Ready to implement Phase 2. See IMPLEMENTATION_GUIDE.md for code.
