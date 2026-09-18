# Phase 2 Research & Decisions - Working Document

**Status:** Awaiting research agent findings (5+ minutes in progress)  
**Last Updated:** 2026-09-18  
**Action Items:** To be filled in as research completes

---

## Summary of Decisions Made So Far

### Architecture Locked In ✅
1. **Brain Structure:** Markdown Obsidian vault (ROBUST, 15/15 tests passing)
2. **Model Selection:** Haiku (subagents) + Sonnet (leads), all low effort
3. **Execution Model:** Autonomous (no approval gates, lead-managed teams)
4. **Departments:** 4 (Marketing, Support, Engineering, Research)
5. **Agents:** 11 total (realistic vs. original 35)
6. **MCP Tools:** Web Search + Documents + Deployment

### Brain Architecture Validation ✅
```
Stress Tests: 15/15 passing
- 100+ notes: efficient
- Circular links: no crashes
- Broken links: degrade gracefully
- Unicode/UTF-8: supported
- Deep nesting (5+ levels): works
- Large files (2MB+): handled
- Permission errors: caught
- Relevance ranking: accurate

Conclusion: Obsidian markdown vaults are production-ready for Phase 2
```

### LangGraph StateGraph Design ✅
```python
OfficeState:
  task_id, task_text, department
  status: pending → assigned → in_progress → completed
  assigned_lead, assigned_agents
  brain_context, messages, working_memory
  deliverable, used_tools, errors

Execution Flow:
  Router → Brain Context → Lead Plans → Parallel Specialists → Synthesis → Brain Update → Complete
  
Key: NO approval gates (autonomous execution)
```

### Department Structure (PROPOSED)
```
Department          Lead Agent        Specialists (3)              Team Size
─────────────────────────────────────────────────────────────────────────
Marketing           Marketing Lead    Research, Copy, Analytics    3
Support             Support Lead      Support, Financial, Research 3  
Engineering         Eng Lead          Backend, Frontend, DevOps     3
Research            Research Lead     Web Researcher, Analyst       2
─────────────────────────────────────────────────────────────────────────
TOTAL                                                               11 agents
```

**Rationale:** Based on agentic OS patterns (AutoGPT, LangChain, CrewAI)

---

## Pending Research Agent Findings

### Topic 1: Agentic OS Department Structures
**Status:** 🔄 IN PROGRESS  
**Expected:** Templates from AutoGPT, LangChain, CrewAI, Claude Projects  
**Will Provide:**
- Real department structures (department count, agent roles)
- Agent count benchmarks
- Hierarchy patterns (Lead vs Specialist)
- Specialization areas

### Topic 2: Agent Guardrail Templates
**Status:** 🔄 IN PROGRESS  
**Expected:** Best practices from production agentic systems  
**Will Provide:**
- Guardrail structure template
- Constraint examples by agent type
- Escalation rules
- Tool access patterns

### Topic 3: MCP Tools Availability
**Status:** 🔄 IN PROGRESS  
**Expected:** Catalog of available MCPs  
**Will Provide:**
- Web Search MCP capabilities
- Document MCPs (Google Drive vs Notion vs others)
- Deployment MCPs (what exists besides Ansible)
- Tool integration patterns with LangGraph

### Topic 4: Agent Skills & Capabilities
**Status:** 🔄 IN PROGRESS  
**Expected:** How top platforms define agent skills  
**Will Provide:**
- Skill definition format
- Skill templates (e.g., "web_search", "write_document")
- Skill composition (how skills combine)
- Standard skill library

### Topic 5: LangGraph Multi-Agent Patterns
**Status:** 🔄 IN PROGRESS  
**Expected:** LangChain documentation + examples  
**Will Provide:**
- Multi-agent orchestration patterns
- Team coordination approaches
- Message passing architecture
- State management for multiple agents

---

## Questions Arising

### Q1: Department Structure
Your proposal: 4 departments, 11 agents  
**Research will answer:** Do real systems use similar counts? Is this the right level of granularity?

### Q2: Specialist vs Lead Hierarchy
Your requirement: Autonomous execution (no user approval)  
**Research will answer:** How do top systems handle lead approval within departments? How do leads escalate?

### Q3: MCP Tool Integration
Your tools: Web Search, Documents, Deployment  
**Research will answer:**
- Which MCP servers are stable/recommended?
- How complex is LangGraph + MCP integration?
- Any missing tools for your use cases?

### Q4: Brain Metadata
Our plan: Add YAML frontmatter to notes  
**Research will answer:** What metadata do real systems attach? Tags, types, ownership, versioning?

### Q5: Agent Learning
Your workflow: Agents update brain with findings  
**Research will answer:** How do systems handle knowledge update conflicts? Versioning? Rollback?

---

## Next Steps (Waiting For Research)

1. ✅ **Complete:** Brain robustness validation
2. ✅ **Complete:** LangGraph state design
3. ✅ **Complete:** Department structure proposal
4. 🔄 **IN PROGRESS:** Research findings
5. **NEXT:** Finalize department & agent structure based on real templates
6. **NEXT:** Update IMPLEMENTATION_PLAN.md with concrete agent definitions
7. **NEXT:** Begin Phase 2 implementation

---

## Files Updated This Session

- `PHASE_1_READY.md` - Phase 1 completion summary
- `PHASE_2_DESIGN.md` - Phase 2 orchestration plan
- `backend/tests/test_brain_robustness.py` - 15 robustness tests
- `PHASE_2_RESEARCH_FINDINGS.md` - This file (working doc)

---

## When Research Completes

You'll see a message like:
```
Research agent completed. Findings show:
- Department structures from [systems]
- [N] guardrail templates
- [N] MCP tools available
- Agent skill patterns
```

Then we'll:
1. Incorporate findings into PHASE_2_DESIGN.md
2. Finalize agent definitions
3. Begin Phase 2 implementation
4. Ask any final clarifying questions

---

**Awaiting research completion... ETA: ~2-5 minutes**
