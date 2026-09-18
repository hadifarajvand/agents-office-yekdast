# Agents Office → LangGraph/LangChain Migration Architecture

**Goal:** Rewrite agents-office backend using LangGraph or LangChain for explicit orchestration, sandboxing, and extensibility while maintaining the 35-agent office metaphor.

---

## Executive Summary

| Aspect | Current (Direct Claude) | LangGraph Option | LangChain Option |
|--------|------------------------|------------------|------------------|
| **Orchestration** | Implicit (prompt-driven) | Explicit graphs + StateGraph | Supervisor chains + agents |
| **State Management** | Loose (task.json + notes) | Centralized snapshots | Context window + memory |
| **Multi-Agent** | Sequential subprocess spawns | Parallel graph nodes | Built-in agent supervisor |
| **Tool Sandboxing** | MCP servers + file access | External + container execution | External + container execution |
| **Learning Curve** | Minimal | Steep (graph theory) | Medium (chains → agents) |
| **Production Readiness** | ✓ 3.6+ stable | ✓ 2025 GA | ✓ 2025 LangGraph Platform GA |
| **MCP Integration** | Native | Via langchain-mcp-adapters | Via MCPAdapter |

---

## Current Architecture (agents-office v3.6)

### Execution Flow
```
User Input (task bar)
  ↓
Routing Call (Claude → pick agent/department)
  ↓
Agent Task Execution:
  • Prompt built: agent role + brief + skills + learned rules + brain context
  • CLI spawn: `claude -p --model=<model> [--effort=...] [--chrome]`
  • SDK call: sdk.messages.create() if ANTHROPIC_API_KEY set
  • Tools: MCP servers (Slack, Gmail, Notion, etc.) + web search + browser
  ↓
Deliverable saved to <brain>/Agents Office/<date>-<agent-id>.md
  ↓
Brain graph rebuilt (wiki-link analysis)
  ↓
Chat turn (message → agent response in persona)
```

### Key Components
- **Roster** (office.agents.json): 35 agents × 6 departments, each with id/role/does/brief
- **Skills** (skills/ + <brain>/Agents Office/skills/): 3-step workflows with templates
- **Routing**: Claude names the best agent; no graph or stateful logic
- **Learning**: revise: → feedback/*.md → rules re-read before next task
- **Teams** (V3.2): Lead splits work, runs 2-4 teammates in parallel, merges results
- **Routines** (V3.5): Timetable in routines.json, clock-driven by server, state in data/routines.json
- **MCP**: office.config.json controls allow/deny + per-department wiring

---

## Why LangGraph for Agents Office

LangGraph excels at orchestration problems requiring:
- **Explicit branching**: Task → route → agent team vs single agent vs escalation
- **Approval gates**: Draft → WAITING ON APPROVAL → human decision → execute or revise
- **Long-running orchestration**: Routines firing on schedule, catch-ups after downtime
- **Parallel execution**: Teams (lead + 2-4 teammates working simultaneously)
- **State recovery**: Crashes during routines restore from checkpoint

Current agents-office does these implicitly (prompt-driven). LangGraph makes them **first-class citizens**.

---

## Proposed LangGraph Architecture

### 1. Core State Graph

```python
from langgraph.graph import StateGraph, START, END
from typing import TypedDict, Optional, List
from dataclasses import dataclass, field

class OfficeState(TypedDict):
    """Central state for all office operations"""
    # Task metadata
    task_id: str
    department: str
    agent_id: Optional[str]  # set by routing
    task_text: str
    model: str  # sonnet | opus | fable
    effort: str  # auto | low | medium | high | xhigh | max
    
    # Execution
    routing_result: Optional[dict]  # {agent_id, reason}
    deliverable: Optional[str]  # markdown from agent
    chat_context: List[dict]  # conversation history
    used_tools: List[str]  # [Gmail, Notion, web]
    
    # Approval workflow
    needs_approval: bool
    approval_status: str  # pending | approved | rejected
    rejection_feedback: Optional[str]
    
    # Team execution
    is_team_task: bool
    team_pieces: List[dict]  # {agent_id, subtask, piece_result}
    team_notes: List[dict]  # {from_agent, to, note}
    
    # Brain context
    relevant_notes: List[dict]  # [{title, path, content}]
    
    # Metadata
    created_at: int  # timestamp
    retry_count: int
    error: Optional[str]
```

### 2. Node Implementations

```python
# Node 1: Load context (brain notes + agent brief + skills + learned rules)
async def load_context(state: OfficeState) -> dict:
    """Read brain folder, find relevant notes for task"""
    brain_path = config['brain']
    notes = read_vault(brain_path)
    relevant = rank_by_relevance(notes, state['task_text'], top_k=10)
    
    agent_brief = load_roster()[state['agent_id']]['brief']
    skills = load_skills(brain_path)[state['agent_id']]
    learned_rules = load_learned_rules(brain_path)[state['agent_id']]
    
    return {
        'relevant_notes': relevant,
        'agent_brief': agent_brief,
        'skills': skills,
        'learned_rules': learned_rules
    }

# Node 2: Route (pick agent if not specified)
async def route_task(state: OfficeState) -> dict:
    """If no agent_id, call Claude to pick best agent"""
    if state.get('agent_id'):
        return {}  # already routed
    
    routing_prompt = f"""
    Pick the best agent from this roster for: {state['task_text']}
    
    Departments: {format_roster()}
    
    Return JSON: {{"agent_id": "...", "reason": "..."}}
    """
    
    result = await claude_call(routing_prompt, model='sonnet')
    return {'routing_result': json.loads(result)}

# Node 3: Single agent execution
async def run_agent(state: OfficeState) -> dict:
    """Execute task via Claude with context + tools"""
    agent_id = state['routing_result']['agent_id'] or state['agent_id']
    agent = load_roster()[agent_id]
    
    system_prompt = build_system_prompt(
        agent=agent,
        brief=state['agent_brief'],
        skills=state['skills'],
        learned_rules=state['learned_rules'],
        business=config['name']
    )
    
    user_prompt = f"""
    Task: {state['task_text']}
    
    Brain context:
    {format_notes(state['relevant_notes'])}
    """
    
    # Get MCP tools allowed for this agent
    tools = mcp.get_tools(agent_id, state['department'])
    
    response = await claude_call_with_tools(
        system=system_prompt,
        user=user_prompt,
        tools=tools,
        model=state['model'],
        effort=state['effort']
    )
    
    return {
        'deliverable': response['text'],
        'used_tools': response['tool_calls'],
        'agent_id': agent_id
    }

# Node 4: Check if approval needed
def route_approval(state: OfficeState) -> str:
    """Route based on whether deliverable writes/sends/pays/deletes"""
    if needs_approval_for_outbound_action(state['deliverable']):
        return 'approval'
    return 'save'

# Node 5: Approval gate (human-in-the-loop)
async def wait_for_approval(state: OfficeState) -> dict:
    """Wait for /approve or /reject; learn from rejection"""
    # Poll /api/approvals until decision made
    while True:
        decision = check_approval_endpoint(state['task_id'])
        if decision:
            break
        await asyncio.sleep(1)
    
    if decision['action'] == 'approved':
        return {'approval_status': 'approved'}
    else:
        # Learn from rejection
        feedback = decision.get('feedback', '')
        store_lesson(state['agent_id'], feedback, state['task_id'])
        return {
            'approval_status': 'rejected',
            'rejection_feedback': feedback
        }

# Node 6: Save deliverable
async def save_deliverable(state: OfficeState) -> dict:
    """Write to <brain>/Agents Office/<date>-<agent-id>.md"""
    agent = load_roster()[state['agent_id']]
    timestamp = datetime.now().isoformat()
    filename = f"{timestamp[:10]}-{state['agent_id']}.md"
    
    content = f"""# {agent['name']}: {state['task_text'][:60]}

**Task:** {state['task_text']}
**Model:** {state['model']} (effort: {state['effort']})
**Used:** {', '.join(state['used_tools']) or 'None'}

## Deliverable

{state['deliverable']}

## Context read

{format_backlinks(state['relevant_notes'])}
"""
    
    path = f"{config['brain']}/Agents Office/{filename}"
    fs.write(path, content)
    rebuild_graph()
    
    return {'saved_at': path}

# Node 7: Team execution (parallel)
async def run_team(state: OfficeState) -> dict:
    """Lead splits task, run 2-4 teammates in parallel"""
    lead = load_roster()[state['agent_id']]  # should be a lead
    
    # Step 1: Lead plans the pieces
    planning_prompt = f"""
    Split this task into 2-4 independent pieces for your team:
    {state['task_text']}
    
    Team:
    {format_team_roster(state['department'])}
    
    Return JSON: [
      {{"agent_id": "...", "subtask": "..."}},
      ...
    ]
    """
    
    pieces_raw = await claude_call(planning_prompt, model=state['model'])
    pieces = json.loads(pieces_raw)
    
    # Step 2: Run all teammates in parallel
    async def run_piece(piece):
        agent = load_roster()[piece['agent_id']]
        result = await run_agent({
            **state,
            'agent_id': piece['agent_id'],
            'task_text': piece['subtask']
        })
        return {**piece, 'piece_result': result['deliverable']}
    
    results = await asyncio.gather(*[run_piece(p) for p in pieces])
    
    # Step 3: Lead merges
    merge_prompt = f"""
    Merge these pieces from your team into one deliverable:
    
    {format_pieces(results)}
    
    Final:
    """
    
    merged = await claude_call(merge_prompt, model=state['model'])
    
    return {
        'is_team_task': True,
        'team_pieces': results,
        'deliverable': merged
    }
```

### 3. Graph Definition

```python
def build_office_graph():
    """Build the state graph for a single task execution"""
    graph = StateGraph(OfficeState)
    
    # Nodes
    graph.add_node('load_context', load_context)
    graph.add_node('route', route_task)
    graph.add_node('run_agent', run_agent)
    graph.add_node('check_approval', route_approval)  # actually a conditional edge
    graph.add_node('wait_approval', wait_for_approval)
    graph.add_node('save', save_deliverable)
    graph.add_node('run_team', run_team)
    
    # Edges
    graph.add_edge(START, 'load_context')
    graph.add_edge('load_context', 'route')
    
    # Route based on team flag
    def route_agent_or_team(state):
        return 'run_team' if state.get('is_team_task') else 'run_agent'
    
    graph.add_conditional_edges('route', route_agent_or_team)
    
    # After agent/team execution
    graph.add_edge('run_agent', 'check_approval')
    graph.add_edge('run_team', 'check_approval')
    
    # Approval conditional
    def needs_approval_check(state):
        return 'wait_approval' if state.get('needs_approval') else 'save'
    
    graph.add_conditional_edges('check_approval', needs_approval_check)
    
    # Approval results
    def approval_outcome(state):
        return 'save' if state['approval_status'] == 'approved' else END
    
    graph.add_conditional_edges('wait_approval', approval_outcome)
    
    # Save to end
    graph.add_edge('save', END)
    
    return graph.compile(checkpointer=PostgresCheckpointer(...))
    # or: MemorySaver() for dev, FileSystemSaver() for simple persistence
```

### 4. Routine Orchestration (Separate Graph)

```python
class RoutineState(TypedDict):
    """State for routine execution (timetable-driven)"""
    routine_id: str
    department: str
    agent_id: str
    task_text: str
    when: dict  # {kind, days, at, ...}
    scheduled_at: int  # next fire time (ms)
    last_run: Optional[int]
    status: str  # active | paused | overdue
    catches_up: bool  # marked LATE if missed while office was off
    
def build_routine_graph():
    """Separate graph for timetable-driven work"""
    graph = StateGraph(RoutineState)
    
    # Nodes
    graph.add_node('check_schedule', check_routine_schedule)  # is it time?
    graph.add_node('setup_task', lambda s: {..., 'task_text': s['text']})
    graph.add_node('execute', run_agent)  # reuse office graph node
    graph.add_node('record_run', record_routine_run)
    graph.add_node('schedule_next', schedule_next_run)
    
    # Edges (simplified)
    graph.add_edge(START, 'check_schedule')
    graph.add_conditional_edges('check_schedule', 
        lambda s: 'setup_task' if s['status'] == 'active' else END)
    graph.add_edge('setup_task', 'execute')
    graph.add_edge('execute', 'record_run')
    graph.add_edge('record_run', 'schedule_next')
    graph.add_edge('schedule_next', END)
    
    return graph.compile()
```

---

## Sandboxing & Tool Execution Strategy

### Option A: Container-Based (Recommended for Demo)

```dockerfile
# Dockerfile for agent sandbox
FROM python:3.11-slim

WORKDIR /agent

# Minimal filesystem
RUN mkdir -p /agent/workspace /agent/tools

# Install runtime only (no build tools)
RUN pip install --no-cache-dir \
    requests \
    pydantic \
    openai  # Claude SDK

# Default deny policy
RUN adduser --disabled-password --gecos "" agent && \
    chown -R agent:agent /agent

USER agent

# Entrypoint: receive tool call JSON, execute, return result
ENTRYPOINT ["python", "-m", "agent.sandbox"]
```

**How it works:**
1. Agent generates code to call an external tool (e.g., "read Gmail")
2. Code is NOT executed directly; JSON is sent to sandbox container
3. Container unpacks tool call, validates against whitelist, executes
4. Result returned as JSON
5. Agent uses result in next reasoning step

**Advantages:**
- No direct tool access from LangGraph process
- Escape in sandbox doesn't reach your infra
- MCP servers can still live in sandbox or on host
- Scale horizontally with Kubernetes

### Option B: Subprocess Isolation (Lightweight)

```python
import subprocess
import json

async def execute_tool_safely(tool_call: dict, agent_id: str) -> dict:
    """Execute tool in subprocess with resource limits"""
    
    # Whitelist check
    if tool_call['tool'] not in ALLOWED_TOOLS_FOR[agent_id]:
        raise PermissionError(f"Agent {agent_id} cannot use {tool_call['tool']}")
    
    # Run in subprocess with timeout + resource limits
    try:
        result = await asyncio.wait_for(
            asyncio.create_subprocess_exec(
                'python', '-m', 'agent.tool_runner',
                '--tool', tool_call['tool'],
                '--input', json.dumps(tool_call['input']),
                '--agent', agent_id,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE
            ),
            timeout=30  # 30s max per tool call
        )
        stdout, stderr = await result.communicate()
        if result.returncode != 0:
            raise RuntimeError(f"Tool failed: {stderr.decode()}")
        return json.loads(stdout)
    except asyncio.TimeoutError:
        raise RuntimeError(f"Tool {tool_call['tool']} exceeded 30s timeout")
```

### Option C: Kubernetes Agent Sandbox (Scale)

```yaml
# agent-sandbox-crd.yaml
apiVersion: agentsandbox.kubernetes.io/v1
kind: AgentSandbox
metadata:
  name: task-{{ task_id }}
spec:
  agent:
    image: agents-office:latest
    env:
      AGENT_ID: "{{ agent_id }}"
      TASK_ID: "{{ task_id }}"
  resources:
    limits:
      cpu: "1"
      memory: "512Mi"
  tools:
    - name: gmail
      endpoint: "mcp://gmail.anthropic.com"
      credentials: secretRef
    - name: notion
      endpoint: "mcp://notion.anthropic.com"
  network:
    egress:
      - to: "mcp.anthropic.com"
      - to: "api.openai.com"
    deny:
      - to: "*"  # default deny
  ttl: 3600  # auto-cleanup
```

---

## MCP Integration Layer

### 1. MCP Tool Adapter

```python
from langchain_mcp_adapters import MCPAdapter

class OfficeToolManager:
    """Centralized MCP tool management for agents"""
    
    def __init__(self, mcp_servers_config: dict):
        self.adapters = {}
        self.tools_by_agent = {}
        self.tools_by_dept = {}
        
        # Initialize adapters for each MCP server
        for server_name, server_config in mcp_servers_config.items():
            self.adapters[server_name] = MCPAdapter.from_config(server_config)
    
    async def load_tools(self):
        """Discover all tools from MCP servers"""
        all_tools = {}
        for server_name, adapter in self.adapters.items():
            tools = await adapter.discover_tools()
            all_tools[server_name] = tools
        
        # Apply office config (allow/deny/departments)
        self.filter_by_config(all_tools)
    
    def filter_by_config(self, tools: dict):
        """Apply office.config.json rules"""
        config = load_config()
        
        # Deny list
        if config['mcp'].get('deny'):
            for server in config['mcp']['deny']:
                tools.pop(server, None)
        
        # Department-specific routing
        for server_name, depts in config['mcp'].get('departments', {}).items():
            self.tools_by_dept[server_name] = depts
    
    def get_tools_for_agent(self, agent_id: str, dept: str) -> list:
        """Return tools callable by this agent"""
        agent = load_roster()[agent_id]
        tools = []
        
        # Agent's preferred tools
        for tool_name in agent.get('tools', []):
            if tool_name in self.adapters:
                tools.extend(self.adapters[tool_name].tools)
        
        # Department-routed tools
        for server_name, depts in self.tools_by_dept.items():
            if dept in depts and server_name in self.adapters:
                tools.extend(self.adapters[server_name].tools)
        
        return tools
```

### 2. Tool Execution Wrapper

```python
class SafeToolExecutor:
    """Execute MCP tools through sandbox + audit trail"""
    
    async def execute(self, 
                     tool_call: dict,
                     agent_id: str,
                     task_id: str,
                     sandbox: ContainerExecutor) -> dict:
        """
        1. Audit log the call
        2. Check permissions
        3. Execute in sandbox
        4. Record outcome
        """
        
        # Step 1: Audit
        audit_entry = {
            'timestamp': datetime.now().isoformat(),
            'task_id': task_id,
            'agent_id': agent_id,
            'tool': tool_call['name'],
            'input': tool_call['args'],  # may contain PII
        }
        log_to_audit_trail(audit_entry)
        
        # Step 2: Permission check
        agent = load_roster()[agent_id]
        if tool_call['name'] not in agent.get('tools', []):
            raise PermissionError(f"Agent {agent_id} not authorized for {tool_call['name']}")
        
        # Step 3: Execute (in sandbox)
        try:
            result = await sandbox.run(
                tool_call,
                timeout_sec=30,
                memory_limit_mb=256
            )
            
            # Step 4: Record success
            audit_entry['status'] = 'success'
            audit_entry['output'] = result[:100]  # truncate for storage
            log_to_audit_trail(audit_entry)
            
            return result
            
        except Exception as e:
            audit_entry['status'] = 'error'
            audit_entry['error'] = str(e)
            log_to_audit_trail(audit_entry)
            raise
```

---

## Migration Path (Phased)

### Phase 1: Parallel Run (Month 1)
- Deploy LangGraph backend alongside existing Claude CLI
- Route 10% of tasks through LangGraph, 90% through CLI (canary)
- Compare deliverables, latency, tool usage
- Freeze office.config.json, skills, roster format (shared between backends)

### Phase 2: Expand Coverage (Month 2)
- Move single-agent tasks to LangGraph (marketing, sales, delivery)
- Keep routine/team logic on CLI (complex, lower priority)
- Run A/B tests: Claude CLI vs LangGraph on same tasks
- Metrics: latency, tool success rate, user satisfaction (revise feedback)

### Phase 3: Advanced Features (Month 3)
- Implement team execution in LangGraph (parallel nodes)
- Implement routine orchestration (RoutineState graph)
- Integrate sandboxing (Option A: containers, Option B: subprocesses)
- Migrate approval gates from polling to graph conditional edges

### Phase 4: Full Migration (Month 4)
- All tasks on LangGraph
- CLI backend deprecated
- Gradual rollout of sandboxing (start with read-only tools, then write)
- Kubernetes deployment if needed

---

## Key Configuration Changes

### Python Structure
```
agents-office-py/
├── langgraph/
│   ├── __init__.py
│   ├── graphs.py          # StateGraph definitions (office, routine, team)
│   ├── nodes.py           # node functions (load_context, route, run_agent, ...)
│   ├── state_schema.py    # TypedDict definitions
│   ├── checkpointer.py    # PostgreSQL or FileSystem persistence
│   └── utils.py           # helpers
├── mcp/
│   ├── tool_manager.py    # MCPAdapter wrapper
│   ├── safe_executor.py   # sandbox integration
│   └── audit.py           # permission + audit logging
├── sandbox/
│   ├── container.py       # Docker executor
│   ├── subprocess.py      # Lightweight subprocess executor
│   └── k8s_crd.yaml       # Kubernetes Agent Sandbox
├── backend.py             # FastAPI routes (replace serve.mjs)
├── config.py              # config loading (replaces config.mjs)
├── roster.py              # agent loading (replaces roster.mjs)
└── brain.py               # vault reading (replaces graph-build.mjs)
```

### API Compatibility
Keep `/api/*` endpoints identical:
- POST `/api/tasks` → creates OfficeState, runs graph
- POST `/api/tasks/:id/approve` → sets approval_status
- POST `/api/chat/:id` → creates chat message, re-runs with new message
- GET `/api/skills` → returns skills list (same shape)
- POST `/api/routines` → creates RoutineState, scheduled by server clock

**No frontend changes needed** — agents-office v3.6 UI talks to `/api/*`, backend swaps transparently.

---

## Advantages of LangGraph vs Direct Claude

| Requirement | Direct Claude | LangGraph |
|-------------|---------------|-----------|
| Task routing (pick agent) | Prompt-driven ✓ | Explicit node, testable ✓ |
| Approval gates | Poll-based, ad-hoc | Conditional edge, checkpoints ✓ |
| Parallel teams | `asyncio.gather()` on CLI spawns | Native parallel nodes ✓ |
| Routine scheduling | Custom clock in serve.mjs | RoutineState graph, re-runnable ✓ |
| Sandboxing | File access at spawn-time | Every tool in sandbox, audited ✓ |
| Tool versioning | MCP servers update independently | Adapter layer abstracts, testable ✓ |
| Error recovery | Restart entire task | Checkpoint after each node ✓ |
| Observability | Logs, no trace | Built-in graph traces, latency breakdowns ✓ |
| Testing | Mock Claude, hard to test flow | Unit test each node, mock graph ✓ |

---

## Recommended Next Steps

1. **Set up LangGraph project skeleton** (Python 3.11+)
   ```bash
   pip install langgraph langchain langchain-mcp-adapters python-anthropic
   ```

2. **Implement core graph** (OfficeState + load_context → route → run_agent → save)

3. **Add test harness** (unit tests for each node, integration tests with mocked Claude)

4. **Parallel deployment** (dual backend via environment variable, canary 10%)

5. **Measure & iterate** (latency, cost, deliverable quality vs CLI)

6. **Extend to teams + routines** (RoutineState graph, parallel execution)

7. **Add sandboxing** (start with container option, measure overhead)

---

## References

- **LangGraph Docs:** https://docs.langchain.com/langgraph
- **LangChain MCP:** https://github.com/langchain-ai/langchain-mcp-adapters
- **Multi-Agent Patterns:** https://www.truefoundry.com/blog/multi-agent-architecture
- **Agent Sandboxing:** https://northflank.com/blog/how-to-sandbox-ai-agents
- **Current agents-office:** https://github.com/ajsahni/agents-office
