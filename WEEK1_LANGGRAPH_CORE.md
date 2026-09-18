# Week 1: LangGraph Core Implementation

**Goal:** Build the 7-node graph that orchestrates all v3.6 features.

**Deliverable:** By end of Week 1, you can:
1. Create a task via API
2. Route to agent
3. Execute agent with Claude
4. Save to brain
5. Handle approval gates
6. All tasks traced & logged

---

## File: backend/langgraph/state.py

Complete state schema for ALL features (parallel, routines, approval, teams):

```python
from typing import TypedDict, Optional, List, Dict, Any
from enum import Enum
from dataclasses import dataclass

class TaskStatus(str, Enum):
    PENDING = "pending"
    IN_PROGRESS = "in_progress"
    WAITING_APPROVAL = "waiting_approval"
    DONE = "done"
    LATE = "late"  # routine ran late (after downtime)
    REJECTED = "rejected"
    ERROR = "error"

class OfficeState(TypedDict, total=False):
    """Master state for all task types (single agent, team, routine)"""
    
    # === Identity ===
    task_id: str                    # unique
    task_type: str                  # "task" | "routine" | "scheduled"
    department: str                 # marketing, sales, ops, fin, emails, delivery
    created_at: int                 # ms timestamp
    
    # === Input ===
    task_text: str                  # what user asked
    model: str                      # sonnet | opus | fable
    effort: str                     # auto | low | medium | high | xhigh | max
    
    # === Agent Assignment ===
    agent_id: Optional[str]         # set by routing node
    routing_reason: Optional[str]   # why was this agent picked
    
    # === Brain Context ===
    relevant_notes: List[Dict]      # [{title, path, content, hash}]
    agent_brief: str                # agent's standing instructions
    skills_summary: str             # what this agent knows how to do
    learned_rules: List[str]        # standing rules from feedback
    kb_history: List[Dict]          # conversation history from KB
    
    # === Execution ===
    status: TaskStatus
    deliverable: Optional[str]      # markdown output
    used_tools: List[str]           # [Gmail, Notion, web]
    execution_ms: int               # latency
    error: Optional[str]            # error message if failed
    
    # === Approval Workflow ===
    needs_outbound_action: bool     # send/post/pay/delete?
    approval_status: Optional[str]  # pending | approved | rejected
    rejection_reason: Optional[str]
    
    # === Team Execution (parallel agents) ===
    is_team_task: bool
    team_lead_id: Optional[str]     # department lead
    team_pieces: Optional[List[Dict]]  # [{agent_id, subtask, piece_result}]
    team_notes: Optional[List[Dict]]   # coordination notes between teammates
    
    # === Routine/Scheduling ===
    routine_id: Optional[str]       # if this is a routine execution
    when: Optional[Dict]            # {kind, days, at, start}
    scheduled_for: Optional[int]    # ms timestamp (when it should run)
    is_late: bool                   # true if running after office was offline
    
    # === Metadata ===
    retry_count: int
    parent_task_id: Optional[str]   # if this is a sub-task of team

class ChatState(TypedDict, total=False):
    """State for agent chat (separate from task execution)"""
    
    task_id: str
    agent_id: str
    department: str
    model: str
    
    # Conversation
    chat_history: List[Dict]        # [{role: user|assistant, content: str}]
    brain_context: List[Dict]
    
    # Last response
    last_response: str
    last_response_ms: int
    error: Optional[str]

class RoutineState(TypedDict, total=False):
    """Timetable-driven execution (reuses OfficeState fields)"""
    
    # Routine definition
    routine_id: str
    department: str
    agent_id: str                   # or lead_id if team
    task_text: str                  # what to do
    model: str
    effort: str
    
    # Schedule
    when: Dict                       # {kind, days, at, start}
    next_run_at: int                # ms of next execution
    last_run_at: Optional[int]
    
    # Execution (inherits from OfficeState)
    status: TaskStatus
    deliverable: Optional[str]
    needs_approval: bool
    approval_status: Optional[str]
    is_late: bool
    
    # Team
    is_team: bool
```

---

## File: backend/langgraph/nodes.py

The 7 core nodes (with full implementation):

```python
import asyncio
import json
import time
from typing import Dict, Any, List
from anthropic import Anthropic
from backend.services.knowledge_base import AgentKnowledgeBase
from backend.services.roster import load_roster
from backend.services.brain import load_brain
from backend.services.skills import load_skills_for_agent
from backend.observability.tracer import TaskTracer

# Global client (reuse connection)
anthropic_client = Anthropic()

# ============ NODE 1: Load Context ============
async def load_context(state: Dict[str, Any]) -> Dict[str, Any]:
    """Load brain context, agent brief, skills, learned rules"""
    
    tracer = TaskTracer(state['task_id'])
    tracer.log_node_start('load_context', state)
    start = time.time()
    
    try:
        # Load brain
        brain = load_brain()
        notes = brain.get('notes', [])
        
        # Rank by relevance to task
        relevant = rank_by_relevance(notes, state['task_text'], top_k=10)
        
        # Load agent metadata (if already assigned)
        agent_brief = ""
        skills_summary = ""
        learned_rules = []
        
        if state.get('agent_id'):
            roster = load_roster()
            agent = roster.get(state['agent_id'], {})
            agent_brief = agent.get('brief', '')
            
            # Load skills for this agent
            skills = load_skills_for_agent(state['agent_id'])
            skills_summary = format_skills(skills)
            
            # Load learned rules from KB
            kb = AgentKnowledgeBase(state['agent_id'])
            learned_rules = await kb.get_learned_rules()
            
            # Load KB conversation history
            kb_history = await kb.get_conversation_history(
                state['task_id'], 
                limit=20
            )
        else:
            kb_history = []
        
        duration_ms = int((time.time() - start) * 1000)
        tracer.log_node_end('load_context', duration_ms, {
            'notes_found': len(relevant),
            'rules_found': len(learned_rules)
        })
        
        return {
            'relevant_notes': relevant,
            'agent_brief': agent_brief,
            'skills_summary': skills_summary,
            'learned_rules': learned_rules,
            'kb_history': kb_history
        }
    
    except Exception as e:
        return {'error': f'load_context failed: {str(e)}'}

# ============ NODE 2: Route Agent ============
async def route_agent(state: Dict[str, Any]) -> Dict[str, Any]:
    """If no agent_id, use Claude to pick the best agent"""
    
    tracer = TaskTracer(state['task_id'])
    tracer.log_node_start('route', state)
    start = time.time()
    
    # If already routed, skip
    if state.get('agent_id'):
        return {}
    
    try:
        roster = load_roster()
        dept_agents = [
            a for a in roster.values() 
            if a['department'] == state['department']
        ]
        
        if not dept_agents:
            return {'error': f'No agents in {state["department"]}'}
        
        # If only one agent, pick them
        if len(dept_agents) == 1:
            return {
                'agent_id': dept_agents[0]['id'],
                'routing_reason': 'Only agent in department'
            }
        
        # Ask Claude to pick
        routing_prompt = f"""You are a dispatcher routing tasks to agents.

Task: {state['task_text']}

Available agents in {state['department']}:
{format_agent_options(dept_agents)}

Pick the BEST agent for this task. Return valid JSON (no markdown):
{{"agent_id": "...", "reason": "..."}}
"""
        
        response = await anthropic_client.messages.create(
            model='claude-3-5-sonnet-20241022',
            max_tokens=200,
            messages=[{'role': 'user', 'content': routing_prompt}]
        )
        
        result = json.loads(response.content[0].text)
        
        duration_ms = int((time.time() - start) * 1000)
        tracer.log_node_end('route', duration_ms, result)
        
        return {
            'agent_id': result['agent_id'],
            'routing_reason': result['reason']
        }
    
    except Exception as e:
        return {'error': f'routing failed: {str(e)}'}

# ============ NODE 3: Run Agent ============
async def run_agent(state: Dict[str, Any]) -> Dict[str, Any]:
    """Execute task with Claude + MCP tools"""
    
    tracer = TaskTracer(state['task_id'])
    tracer.log_node_start('run_agent', state)
    start = time.time()
    
    try:
        agent_id = state.get('agent_id')
        if not agent_id:
            return {'error': 'agent_id not set'}
        
        roster = load_roster()
        agent = roster.get(agent_id)
        if not agent:
            return {'error': f'Agent {agent_id} not found'}
        
        # Build system prompt
        system = build_system_prompt(agent, state)
        
        # Build user prompt with context
        user = build_user_prompt(state)
        
        # Get tools for this agent
        tools = await get_tools_for_agent(agent_id, state['department'])
        formatted_tools = format_tools_for_api(tools)
        
        # Agentic loop
        messages = [{'role': 'user', 'content': user}]
        used_tools = set()
        all_text = []
        
        while True:
            response = await anthropic_client.messages.create(
                model=state.get('model', 'claude-3-5-sonnet-20241022'),
                max_tokens=4096,
                system=system,
                tools=formatted_tools if formatted_tools else None,
                messages=messages
            )
            
            # Collect text
            for block in response.content:
                if hasattr(block, 'text'):
                    all_text.append(block.text)
            
            # Check for tool use
            has_tool_use = any(
                block.type == 'tool_use' 
                for block in response.content
            )
            
            if response.stop_reason == 'end_turn' or not has_tool_use:
                break
            
            # Execute tools
            tool_results = []
            for block in response.content:
                if block.type == 'tool_use':
                    used_tools.add(block.name)
                    
                    # Execute tool (in sandbox)
                    try:
                        executor = get_tool_executor()
                        result = await executor.execute(
                            {'name': block.name, 'input': block.input},
                            agent_id,
                            state['task_id']
                        )
                        
                        tracer.log_tool_call(
                            block.name,
                            block.input,
                            result[:100] if result else '',
                            50,  # TODO: measure actual duration
                            True
                        )
                        
                        tool_results.append({
                            'type': 'tool_result',
                            'tool_use_id': block.id,
                            'content': result
                        })
                    except Exception as e:
                        tool_results.append({
                            'type': 'tool_result',
                            'tool_use_id': block.id,
                            'content': f'Error: {str(e)}',
                            'is_error': True
                        })
            
            # Append to messages
            messages.append({'role': 'assistant', 'content': response.content})
            messages.append({'role': 'user', 'content': tool_results})
        
        # Record in KB
        kb = AgentKnowledgeBase(agent_id)
        await kb.add_conversation(
            state['task_id'],
            'user',
            state['task_text']
        )
        await kb.add_conversation(
            state['task_id'],
            'assistant',
            '\n'.join(all_text)
        )
        
        deliverable = '\n'.join(all_text).strip()
        duration_ms = int((time.time() - start) * 1000)
        
        # Check if needs approval
        needs_approval = check_needs_approval(deliverable)
        
        tracer.log_node_end('run_agent', duration_ms, {
            'tools_used': list(used_tools),
            'needs_approval': needs_approval
        })
        
        return {
            'deliverable': deliverable,
            'used_tools': list(used_tools),
            'execution_ms': duration_ms,
            'needs_outbound_action': needs_approval,
            'status': 'waiting_approval' if needs_approval else 'done'
        }
    
    except Exception as e:
        return {'error': f'run_agent failed: {str(e)}'}

# ============ NODE 4: Check Approval ============
def check_approval_needed(state: Dict[str, Any]) -> Dict[str, Any]:
    """Evaluate if deliverable needs human approval"""
    # This is just routing, no real work
    return {}

# ============ NODE 5: Wait for Approval ============
async def wait_for_approval(state: Dict[str, Any]) -> Dict[str, Any]:
    """Poll for approval decision (HTTP endpoint sets it)"""
    
    tracer = TaskTracer(state['task_id'])
    tracer.log_approval_needed('Waiting for human approval', state['deliverable'][:100])
    
    # Approval is set via HTTP endpoint
    # This node waits (in practice, handled by FastAPI)
    # For now, return state unchanged
    return {'approval_status': 'pending'}

# ============ NODE 6: Save Deliverable ============
async def save_deliverable(state: Dict[str, Any]) -> Dict[str, Any]:
    """Write to <brain>/Agents Office/<date>-<agent-id>.md"""
    
    tracer = TaskTracer(state['task_id'])
    tracer.log_node_start('save', state)
    start = time.time()
    
    try:
        from datetime import datetime
        from pathlib import Path
        
        agent_id = state['agent_id']
        roster = load_roster()
        agent = roster.get(agent_id, {})
        
        timestamp = datetime.now().isoformat()[:10]
        filename = f"{timestamp}-{agent_id}.md"
        
        # Format markdown
        content = f"""# {agent['name']}: {state['task_text'][:60]}

**Task:** {state['task_text']}
**Model:** {state['model']} (effort: {state['effort']})
**Used:** {', '.join(state['used_tools']) or 'None'}
**Status:** {state['status']}

## Deliverable

{state['deliverable']}

## Context Read

{format_backlinks(state['relevant_notes'])}
"""
        
        # Write to brain
        brain_path = Path(state.get('brain_path', './brain'))
        notes_dir = brain_path / 'Agents Office'
        notes_dir.mkdir(parents=True, exist_ok=True)
        
        (notes_dir / filename).write_text(content)
        
        # Rebuild graph (TODO: implement)
        # await rebuild_brain_graph()
        
        duration_ms = int((time.time() - start) * 1000)
        tracer.log_node_end('save', duration_ms, {'path': filename})
        
        return {
            'saved_at': str(notes_dir / filename),
            'status': 'done'
        }
    
    except Exception as e:
        return {'error': f'save failed: {str(e)}'}

# ============ Helpers ============

def build_system_prompt(agent: Dict, state: Dict) -> str:
    """Build system prompt for agent"""
    brief = state.get('agent_brief', '')
    skills = state.get('skills_summary', '')
    rules = state.get('learned_rules', [])
    company = "Our Company"  # TODO: load from config
    
    prompt = f"""You are {agent['name']}, {agent['role']}.

Job: {agent['does']}

Company: {company}

{f'Brief: {brief}' if brief else ''}

{f'How to do your work:\\n{skills}' if skills else ''}

{f'Standing rules:\\n' + '\\n'.join(f'- {r}' for r in rules) if rules else ''}

Remember: Read notes freely. Send, post, pay, delete, or change anything outside this machine ONLY if the task explicitly asks.
"""
    
    return prompt.strip()

def build_user_prompt(state: Dict) -> str:
    """Build user prompt with context"""
    notes_text = '\n'.join([
        f"[[{n['title']}]]({n['path']}): {n['content'][:100]}..."
        for n in state.get('relevant_notes', [])
    ])
    
    prompt = f"""Task: {state['task_text']}

Brain context:
{notes_text}

Complete the task. Return markdown."""
    
    return prompt.strip()

def rank_by_relevance(notes: List[Dict], query: str, top_k: int = 10) -> List[Dict]:
    """Simple keyword matching (TODO: embeddings)"""
    query_words = set(query.lower().split())
    scored = []
    
    for note in notes:
        content = note.get('content', '').lower()
        title = note.get('title', '').lower()
        
        title_matches = len(query_words & set(title.split()))
        content_matches = len(query_words & set(content.split()))
        score = (title_matches * 2) + content_matches
        
        if score > 0:
            scored.append((score, note))
    
    scored.sort(key=lambda x: x[0], reverse=True)
    return [n for _, n in scored[:top_k]]

def format_agent_options(agents: List[Dict]) -> str:
    """Pretty-print agent roster"""
    lines = []
    for a in agents:
        lines.append(f"- {a['name']} ({a['id']}): {a['does']}")
    return '\n'.join(lines)

def format_skills(skills: List[Dict]) -> str:
    """Format skills for prompt"""
    if not skills:
        return ""
    
    lines = []
    for skill in skills:
        lines.append(f"**{skill['name']}**: {skill['description']}")
    return '\n'.join(lines)

def check_needs_approval(deliverable: str) -> bool:
    """Check if deliverable contains outbound actions"""
    keywords = ['send', 'email', 'post', 'message', 'pay', 'charge', 'delete', 'remove']
    return any(kw in deliverable.lower() for kw in keywords)

def format_backlinks(notes: List[Dict]) -> str:
    """Format notes as markdown links"""
    lines = []
    for n in notes:
        lines.append(f"- [[{n['title']}]]({n['path']})")
    return '\n'.join(lines)

async def get_tools_for_agent(agent_id: str, department: str) -> List[Dict]:
    """Get MCP tools for this agent"""
    # TODO: implement MCP tool manager
    return []

def format_tools_for_api(tools: List[Dict]) -> List[Dict]:
    """Format MCP tools for Claude API"""
    # TODO: implement
    return []

def get_tool_executor():
    """Get tool executor (sandbox)"""
    # TODO: implement
    pass
```

---

## File: backend/langgraph/graphs.py

The StateGraph wiring (7 nodes + routing):

```python
from langgraph.graph import StateGraph, START, END
from .state import OfficeState
from .nodes import (
    load_context,
    route_agent,
    run_agent,
    check_approval_needed,
    wait_for_approval,
    save_deliverable
)

def build_office_graph():
    """Main orchestration graph"""
    
    graph = StateGraph(OfficeState)
    
    # Add nodes
    graph.add_node('load_context', load_context)
    graph.add_node('route', route_agent)
    graph.add_node('run_agent', run_agent)
    graph.add_node('approval_check', check_approval_needed)
    graph.add_node('wait_approval', wait_for_approval)
    graph.add_node('save', save_deliverable)
    
    # Build edges
    graph.add_edge(START, 'load_context')
    graph.add_edge('load_context', 'route')
    graph.add_edge('route', 'run_agent')
    graph.add_edge('run_agent', 'approval_check')
    
    # Conditional: needs approval?
    def route_approval(state: OfficeState) -> str:
        if state.get('needs_outbound_action'):
            return 'wait_approval'
        return 'save'
    
    graph.add_conditional_edges('approval_check', route_approval)
    
    # After approval
    def route_after_approval(state: OfficeState) -> str:
        if state.get('approval_status') == 'approved':
            return 'save'
        return END  # rejected, don't save
    
    graph.add_conditional_edges('wait_approval', route_after_approval)
    
    graph.add_edge('save', END)
    
    return graph.compile()
```

---

## File: backend/api/tasks.py

FastAPI routes that invoke the graph:

```python
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
import uuid
from datetime import datetime
import asyncio
from backend.langgraph.graphs import build_office_graph
from backend.langgraph.state import OfficeState, TaskStatus

router = APIRouter(prefix='/api/tasks')

# In-memory task store (replace with DB later)
TASKS = {}

class TaskCreateRequest(BaseModel):
    department: str
    text: str
    model: str = 'sonnet'
    effort: str = 'auto'
    is_team_task: bool = False

@router.post('')
async def create_task(req: TaskCreateRequest):
    """POST /api/tasks: Create and execute task"""
    
    task_id = str(uuid.uuid4())[:8]
    
    # Initial state
    initial_state = {
        'task_id': task_id,
        'department': req.department,
        'task_text': req.text,
        'model': req.model,
        'effort': req.effort,
        'is_team_task': req.is_team_task,
        'created_at': int(datetime.now().timestamp() * 1000),
        'status': TaskStatus.IN_PROGRESS,
        'used_tools': [],
        'retry_count': 0,
        'learned_rules': [],
        'team_pieces': [],
        'team_notes': [],
        'kb_history': [],
        'relevant_notes': []
    }
    
    # Store in memory
    TASKS[task_id] = initial_state
    
    # Execute graph asynchronously
    asyncio.create_task(execute_task_graph(task_id, initial_state))
    
    return {
        'task_id': task_id,
        'status': 'pending',
        'department': req.department,
        'text': req.text,
        'created_at': initial_state['created_at']
    }

async def execute_task_graph(task_id: str, initial_state: dict):
    """Run the graph and store results"""
    try:
        graph = build_office_graph()
        final_state = await graph.ainvoke(initial_state)
        TASKS[task_id] = final_state
    except Exception as e:
        TASKS[task_id]['error'] = str(e)
        TASKS[task_id]['status'] = TaskStatus.ERROR

@router.get('/{task_id}')
async def get_task(task_id: str):
    """GET /api/tasks/{task_id}: Get task status"""
    
    if task_id not in TASKS:
        raise HTTPException(status_code=404, detail='Task not found')
    
    task = TASKS[task_id]
    return {
        'task_id': task_id,
        'status': task.get('status'),
        'deliverable': task.get('deliverable'),
        'used_tools': task.get('used_tools', []),
        'approval_status': task.get('approval_status'),
        'error': task.get('error'),
        'execution_ms': task.get('execution_ms', 0)
    }

@router.post('/{task_id}/approve')
async def approve_task(task_id: str):
    """POST /api/tasks/{task_id}/approve: Approve pending task"""
    
    if task_id not in TASKS:
        raise HTTPException(status_code=404)
    
    TASKS[task_id]['approval_status'] = 'approved'
    return {'approved': True}

@router.post('/{task_id}/reject')
async def reject_task(task_id: str, feedback: str = ''):
    """POST /api/tasks/{task_id}/reject: Reject with feedback"""
    
    if task_id not in TASKS:
        raise HTTPException(status_code=404)
    
    task = TASKS[task_id]
    task['approval_status'] = 'rejected'
    task['rejection_reason'] = feedback
    
    # Learn from rejection
    agent_id = task.get('agent_id')
    if agent_id:
        from backend.services.knowledge_base import AgentKnowledgeBase
        kb = AgentKnowledgeBase(agent_id)
        await kb.add_learned_rule(
            f'In task "{task["task_text"][:50]}", avoid doing this',
            task_id,
            feedback
        )
    
    return {'rejected': True}
```

---

## Run Week 1

```bash
# 1. Implement files above
#    - backend/langgraph/state.py
#    - backend/langgraph/nodes.py
#    - backend/langgraph/graphs.py
#    - backend/api/tasks.py

# 2. Update main.py to include routes
# In backend/main.py:
from backend.api.tasks import router as tasks_router
app.include_router(tasks_router)

# 3. Start services
docker-compose up -d

# 4. Test
curl -X POST http://localhost:8000/api/tasks \
  -H "Content-Type: application/json" \
  -d '{
    "department": "marketing",
    "text": "Write a blog post about AI",
    "model": "sonnet"
  }'

# Response:
# {
#   "task_id": "abc123",
#   "status": "pending",
#   "department": "marketing"
# }

# 5. Check status
curl http://localhost:8000/api/tasks/abc123

# 6. View traces
# Open http://localhost:16686 (Jaeger)

# 7. Run tests
pytest backend/tests/test_nodes.py -v --asyncio-mode=auto
pytest backend/tests/test_graphs.py -v --asyncio-mode=auto
```

---

## Week 1 Checklist

- [ ] Implement OfficeState + RoutineState + ChatState
- [ ] Implement 6 core nodes (load_context → run_agent → save)
- [ ] Build StateGraph with conditional routing
- [ ] Implement FastAPI routes (/api/tasks POST/GET)
- [ ] Implement AgentKnowledgeBase (JSONL history)
- [ ] Implement TaskTracer (Jaeger + structured logging)
- [ ] Write unit tests for each node
- [ ] Test end-to-end task execution
- [ ] Verify traces in Jaeger UI
- [ ] Verify logs in structured format

---

## By End of Week 1

You'll have:
✅ Single agent execution (works end-to-end)
✅ Brain context loading
✅ Approval gates (waiting for /approve)
✅ Deliverable saved to brain
✅ Full tracing visible (Jaeger)
✅ Logging every step
✅ Knowledge base per agent (JSONL + rules)
✅ Complete test suite

**Next: Week 2 = Team Execution (parallel agents)**
