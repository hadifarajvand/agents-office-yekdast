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

### Proposed Department Structure

Based on agentic OS patterns (AutoGPT, LangChain, CrewAI), departments should be:

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

## 3. Task Execution Model

### Your Requirement: Autonomous Execution
- ✅ NO user approval needed for agent runs
- ✅ Lead agents manage their teams autonomously
- ✅ User only approves/reviews AFTER completion
- ✅ If process is bad, user updates guardrails (not individual tasks)

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

### Phase 2 Tools (Confirmed)
1. **Web Search** - Research, market data, competitor analysis
2. **Documents** - Google Drive / Notion integration
3. **Deployment** - Deployment MCP (TBD: research needed)

### Tools NOT in Phase 2
- ❌ Email (Gmail) - defer to Phase 5
- ❌ Slack - defer to Phase 5
- ❌ Calendar - defer to Phase 5
- ❌ Project Tracking - not needed

### MCP Tool Availability
**PENDING:** Research agent findings on:
- Web Search MCP capabilities
- Document MCP integrations (Google Drive vs Notion)
- Deployment MCPs available
- Tool availability in LangGraph

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

## Outstanding Questions

Awaiting research agent findings on:
1. ✅ Department structures in real agentic systems
2. ✅ Agent guardrail templates
3. ✅ MCP tools availability (web search, documents, deployment)
4. ✅ Agent skill definitions and templates
5. ✅ LangGraph patterns for multi-agent orchestration

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

## Decisions Locked In

✅ **Models:** Haiku (subagents) + Sonnet (leads)  
✅ **Effort:** Low for all agents  
✅ **Autonomy:** No approval gates (autonomous execution)  
✅ **Brain:** Markdown Obsidian vault (robust, tested)  
✅ **Departments:** 4 (Marketing, Support, Engineering, Research)  
✅ **Agents:** 11 (3-3-3-2 split)  
✅ **MCP Tools:** Web Search + Documents + Deployment  
✅ **Frontend:** Ready to send tasks in Phase 2  

---

**Status:** Awaiting research findings → Finalize design → Implement Phase 2
