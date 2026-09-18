# Agents Office + LangGraph: Implementation Quick Start

This guide walks through building a working prototype of agents-office on LangGraph with sandboxing.

---

## Part 1: Project Setup

### 1.1 Python Environment

```bash
# Create virtual env
python3.11 -m venv venv
source venv/bin/activate  # macOS/Linux
# or: venv\Scripts\activate  # Windows

# Install core dependencies
pip install --upgrade pip
pip install langgraph langchain langchain-mcp-adapters python-anthropic
pip install fastapi uvicorn pydantic
pip install psycopg2-binary  # PostgreSQL checkpointer (optional)
pip install pyyaml  # config parsing
pip install pytest  # testing
```

### 1.2 Directory Structure

```
agents-office-langgraph/
├── .env                    # ANTHROPIC_API_KEY, DATABASE_URL
├── config.py               # Load office.config.json
├── main.py                 # FastAPI app
├── requirements.txt
│
├── langgraph/
│   ├── __init__.py
│   ├── state.py            # OfficeState, RoutineState TypedDicts
│   ├── nodes.py            # node functions
│   ├── graphs.py           # StateGraph definitions
│   ├── edges.py            # conditional routing functions
│   └── checkpointer.py     # PostgreSQL/FileSystem persistence
│
├── mcp/
│   ├── __init__.py
│   ├── manager.py          # MCPAdapter wrapper
│   ├── executor.py         # tool execution (sandboxed)
│   ├── audit.py            # audit logging
│   └── whitelist.py        # permission model
│
├── sandbox/
│   ├── __init__.py
│   ├── container.py        # Docker executor
│   ├── subprocess.py       # Lightweight subprocess
│   └── policy.py           # security policy
│
├── services/
│   ├── __init__.py
│   ├── brain.py            # Vault reading (replaces graph-build.mjs)
│   ├── roster.py           # Agent loading
│   ├── skills.py           # Skill loading
│   └── learning.py         # Feedback recording
│
├── api/
│   ├── __init__.py
│   ├── tasks.py            # POST /api/tasks, etc.
│   ├── chat.py             # POST /api/chat/:id
│   ├── approval.py         # POST /api/tasks/:id/approve
│   └── webhooks.py         # routine firing
│
└── tests/
    ├── test_nodes.py
    ├── test_graphs.py
    ├── test_mcp.py
    └── test_sandbox.py
```

---

## Part 2: Core State & Nodes

### 2.1 State Definition (langgraph/state.py)

```python
from typing import TypedDict, Optional, List, Dict, Any
from dataclasses import dataclass
from enum import Enum

class TaskStatus(str, Enum):
    PENDING = "pending"
    IN_PROGRESS = "in_progress"
    WAITING_APPROVAL = "waiting_approval"
    DONE = "done"
    ERROR = "error"

class OfficeState(TypedDict, total=False):
    """Central state for task execution"""
    
    # Identity
    task_id: str
    department: str
    agent_id: Optional[str]
    created_at: int  # ms timestamp
    
    # Input
    task_text: str
    model: str  # sonnet | opus | fable
    effort: str  # auto | low | medium | high | xhigh | max
    
    # Execution
    status: TaskStatus
    routing_reason: Optional[str]  # why was this agent picked?
    
    # Brain context
    relevant_notes: List[Dict[str, str]]  # [{title, path, content, hash}]
    agent_brief: str
    skills_summary: str
    learned_rules: List[str]
    
    # Work done
    deliverable: Optional[str]  # markdown output
    used_tools: List[str]  # [Gmail, Notion, web]
    execution_ms: int  # latency
    
    # Approval workflow
    needs_outbound_action: bool
    approval_status: Optional[str]  # pending | approved | rejected
    rejection_reason: Optional[str]
    
    # Team (if is_team_task)
    is_team_task: bool
    team_pieces: Optional[List[Dict[str, Any]]]
    team_notes: Optional[List[Dict[str, str]]]
    
    # Metadata
    error: Optional[str]
    retry_count: int

class ChatState(TypedDict, total=False):
    """State for chat with an agent"""
    
    task_id: str
    agent_id: str
    department: str
    model: str
    
    chat_history: List[Dict[str, str]]  # [{role: user|assistant, content: ...}]
    brain_context: List[Dict[str, str]]
    
    last_response: str
    error: Optional[str]

class RoutineState(TypedDict, total=False):
    """State for timetable-driven task"""
    
    routine_id: str
    department: str
    agent_id: str
    task_text: str
    model: str
    effort: str
    
    # Schedule
    when: Dict[str, Any]  # {kind, days, at, start, ...}
    next_run_at: int  # ms timestamp of next execution
    last_run_at: Optional[int]
    is_late: bool  # true if running after downtime
    
    # Execution reuses OfficeState fields
    status: TaskStatus
    deliverable: Optional[str]
    used_tools: List[str]
    needs_approval: bool
    approval_status: Optional[str]
```

### 2.2 Node: Load Context (langgraph/nodes.py)

```python
from anthropic import Anthropic
import json
from typing import Any, Dict
from .state import OfficeState

async def load_context(state: OfficeState) -> Dict[str, Any]:
    """Load brain notes, agent brief, skills, learned rules"""
    
    # Read brain folder
    brain = load_brain(config['brain_path'])
    
    # Rank notes by relevance to task
    relevant_notes = rank_notes(brain.all_notes, state['task_text'], top_k=10)
    
    # Load agent metadata
    agent_id = state.get('agent_id')
    if agent_id:
        roster = load_roster()
        agent = roster[agent_id]
        brief = agent.get('brief', '')
        
        # Load skills bound to this agent
        skills = load_skills_for_agent(agent_id)
        skills_summary = format_skills(skills)
        
        # Load learned rules (feedback from revise:)
        learned_rules = load_learned_rules(agent_id)
    else:
        agent = None
        brief = ''
        skills_summary = ''
        learned_rules = []
    
    return {
        'relevant_notes': relevant_notes,
        'agent_brief': brief,
        'skills_summary': skills_summary,
        'learned_rules': learned_rules
    }

def rank_notes(notes: List[Dict], query: str, top_k: int = 10):
    """Use embedding similarity to rank notes"""
    # For MVP: simple keyword matching
    # For production: use sentence-transformers or Claude embeddings
    
    scored = []
    query_words = set(query.lower().split())
    
    for note in notes:
        content = note.get('content', '').lower()
        title = note.get('title', '').lower()
        
        # Score: matches in title weighted 2x
        title_matches = len(query_words & set(title.split()))
        content_matches = len(query_words & set(content.split()))
        score = (title_matches * 2) + content_matches
        
        if score > 0:
            scored.append((score, note))
    
    scored.sort(key=lambda x: x[0], reverse=True)
    return [n for _, n in scored[:top_k]]
```

### 2.3 Node: Route Agent (langgraph/nodes.py)

```python
async def route_agent(state: OfficeState) -> Dict[str, Any]:
    """If no agent_id, pick one using Claude"""
    
    if state.get('agent_id'):
        return {}  # already routed
    
    roster = load_roster()
    dept_agents = [a for a in roster.values() 
                   if a['department'] == state['department']]
    
    routing_prompt = f"""You are a dispatcher for a virtual office.

Department: {state['department']}
Available agents:
{format_agents_for_routing(dept_agents)}

Task: {state['task_text']}

Pick the best agent. Return valid JSON:
{{"agent_id": "...", "reason": "..."}}
"""
    
    client = Anthropic(api_key=config.get('api_key'))
    response = await client.messages.create(
        model='claude-3-5-sonnet-20241022',
        max_tokens=200,
        messages=[{'role': 'user', 'content': routing_prompt}]
    )
    
    try:
        result = json.loads(response.content[0].text)
        return {
            'agent_id': result['agent_id'],
            'routing_reason': result['reason']
        }
    except (json.JSONDecodeError, KeyError):
        # Fallback: pick first agent
        return {'agent_id': dept_agents[0]['id']}

def format_agents_for_routing(agents: List[Dict]) -> str:
    """Pretty-print agent roster"""
    lines = []
    for a in agents:
        lines.append(f"- {a['name']} ({a['id']}): {a['does']}")
    return '\n'.join(lines)
```

### 2.4 Node: Run Agent (langgraph/nodes.py)

```python
async def run_agent(state: OfficeState) -> Dict[str, Any]:
    """Execute task with Claude + tools"""
    import time
    
    start = time.time()
    agent_id = state.get('agent_id')
    
    if not agent_id:
        return {'error': 'agent_id not set'}
    
    roster = load_roster()
    agent = roster[agent_id]
    
    # Build system prompt
    system = f"""You are {agent['name']}, {agent['role']}.

Your job: {agent['does']}

Company: {config.get('name', 'Our company')}

{build_brief_section(state.get('agent_brief', ''))}

{build_skills_section(state.get('skills_summary', ''))}

{build_learned_rules_section(state.get('learned_rules', []))}

Remember: Read notes freely; send, post, pay, delete, or change anything outside this machine **only** if the task explicitly asks for that exact action.
"""
    
    # Build user prompt with context
    user_context = format_notes(state['relevant_notes'])
    
    user = f"""Task: {state['task_text']}

Your notes:
{user_context}

Complete the task. Return markdown.
"""
    
    # Get tools for this agent
    tool_manager = get_mcp_tool_manager()
    tools = await tool_manager.get_tools_for_agent(agent_id, state['department'])
    
    # Execute with Claude
    client = Anthropic(api_key=config.get('api_key'))
    
    messages = [{'role': 'user', 'content': user}]
    model = state.get('model', 'claude-3-5-sonnet-20241022')
    
    # Format tools for Claude API
    formatted_tools = format_tools_for_api(tools)
    
    # Agentic loop: Claude calls tools, we execute, loop until done
    used_tools_names = set()
    all_text = []
    
    while True:
        response = await client.messages.create(
            model=model,
            max_tokens=4096,
            system=system,
            tools=formatted_tools,
            messages=messages
        )
        
        # Collect response
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
        
        # Execute tool calls
        tool_results = []
        for block in response.content:
            if block.type == 'tool_use':
                used_tools_names.add(block.name)
                try:
                    executor = get_tool_executor()
                    result = await executor.execute(
                        tool_call={
                            'name': block.name,
                            'input': block.input
                        },
                        agent_id=agent_id,
                        task_id=state['task_id']
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
        
        # Add assistant response and tool results to messages
        messages.append({'role': 'assistant', 'content': response.content})
        messages.append({'role': 'user', 'content': tool_results})
    
    deliverable = '\n'.join(all_text).strip()
    execution_ms = int((time.time() - start) * 1000)
    
    # Check if deliverable contains outbound action
    needs_approval = check_needs_approval(deliverable)
    
    return {
        'deliverable': deliverable,
        'used_tools': list(used_tools_names),
        'execution_ms': execution_ms,
        'needs_outbound_action': needs_approval,
        'status': 'in_progress'  # will become 'waiting_approval' if needs_approval
    }

def build_brief_section(brief: str) -> str:
    if not brief:
        return ""
    return f"Brief:\n{brief}\n"

def build_skills_section(skills_summary: str) -> str:
    if not skills_summary:
        return ""
    return f"How to do your work:\n{skills_summary}\n"

def build_learned_rules_section(rules: List[str]) -> str:
    if not rules:
        return ""
    rule_text = '\n'.join(f"- {r}" for r in rules)
    return f"Standing rules (learn from previous feedback):\n{rule_text}\n"

def check_needs_approval(deliverable: str) -> bool:
    """Check if deliverable contains send/post/pay/delete"""
    keywords = ['send', 'post', 'email', 'message', 'pay', 'charge', 'delete', 'remove', 'update']
    lower = deliverable.lower()
    return any(kw in lower for kw in keywords)
```

---

## Part 3: Graph Definition

### 3.1 Main Office Graph (langgraph/graphs.py)

```python
from langgraph.graph import StateGraph, START, END
from .state import OfficeState
from .nodes import (
    load_context,
    route_agent,
    run_agent,
    save_deliverable,
    wait_for_approval
)
from .edges import (
    route_to_agent_or_team,
    route_to_approval_or_save,
    route_after_approval
)

def build_office_graph():
    """Main graph for task execution"""
    
    graph = StateGraph(OfficeState)
    
    # Add nodes
    graph.add_node('load_context', load_context)
    graph.add_node('route', route_agent)
    graph.add_node('run_agent', run_agent)
    graph.add_node('approval_check', lambda s: s)  # identity node (routing happens on edges)
    graph.add_node('wait_approval', wait_for_approval)
    graph.add_node('save', save_deliverable)
    
    # Add edges
    graph.add_edge(START, 'load_context')
    graph.add_edge('load_context', 'route')
    graph.add_edge('route', 'run_agent')
    graph.add_edge('run_agent', 'approval_check')
    
    # Conditional: needs approval?
    graph.add_conditional_edges(
        'approval_check',
        route_to_approval_or_save
    )
    
    # Conditional: approval outcome
    graph.add_conditional_edges(
        'wait_approval',
        route_after_approval
    )
    
    graph.add_edge('save', END)
    
    return graph.compile()
```

### 3.2 Edge Functions (langgraph/edges.py)

```python
def route_to_approval_or_save(state: OfficeState) -> str:
    """After agent runs: needs approval?"""
    if state.get('needs_outbound_action'):
        return 'wait_approval'
    else:
        return 'save'

def route_after_approval(state: OfficeState) -> str:
    """After approval decision: approved or not?"""
    if state.get('approval_status') == 'approved':
        return 'save'
    else:
        # rejected: don't save, return to user with feedback
        return END
```

---

## Part 4: FastAPI Server

### 4.1 Task Execution (api/tasks.py)

```python
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
from datetime import datetime
import uuid

router = APIRouter(prefix='/api/tasks')

class TaskCreateRequest(BaseModel):
    department: str
    text: str
    model: str = 'sonnet'
    effort: str = 'auto'
    is_team_task: bool = False

@router.post('')
async def create_task(req: TaskCreateRequest):
    """POST /api/tasks: Create and run task"""
    
    from langgraph import build_office_graph
    
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
        'status': 'pending',
        'used_tools': [],
        'retry_count': 0,
        'is_team_task': req.is_team_task
    }
    
    # Run graph
    graph = build_office_graph()
    
    # Execute asynchronously
    import asyncio
    task = asyncio.create_task(execute_graph_task(graph, initial_state, task_id))
    
    # Store task reference
    RUNNING_TASKS[task_id] = task
    
    return {
        'task_id': task_id,
        'status': 'pending',
        'department': req.department,
        'text': req.text
    }

async def execute_graph_task(graph, initial_state, task_id):
    """Run graph and persist results"""
    try:
        final_state = await graph.ainvoke(initial_state)
        RUNNING_TASKS[task_id] = final_state
        return final_state
    except Exception as e:
        RUNNING_TASKS[task_id] = {
            'error': str(e),
            'task_id': task_id,
            'status': 'error'
        }

@router.get('/{task_id}')
async def get_task(task_id: str):
    """GET /api/tasks/{task_id}: Get task status"""
    task = RUNNING_TASKS.get(task_id)
    if not task:
        raise HTTPException(status_code=404, detail='Task not found')
    
    # Return relevant fields
    return {
        'task_id': task_id,
        'status': task.get('status'),
        'deliverable': task.get('deliverable'),
        'used_tools': task.get('used_tools'),
        'approval_status': task.get('approval_status'),
        'error': task.get('error')
    }

@router.post('/{task_id}/approve')
async def approve_task(task_id: str):
    """POST /api/tasks/{task_id}/approve"""
    task = RUNNING_TASKS.get(task_id)
    if not task:
        raise HTTPException(status_code=404)
    
    task['approval_status'] = 'approved'
    return {'approved': True}

@router.post('/{task_id}/reject')
async def reject_task(task_id: str, feedback: str = ''):
    """POST /api/tasks/{task_id}/reject"""
    task = RUNNING_TASKS.get(task_id)
    if not task:
        raise HTTPException(status_code=404)
    
    task['approval_status'] = 'rejected'
    task['rejection_reason'] = feedback
    return {'rejected': True}
```

### 4.2 Chat Endpoint (api/chat.py)

```python
@router.post('/{task_id}/messages')
async def send_chat_message(task_id: str, message: str):
    """POST /api/tasks/{task_id}/messages: Chat with agent"""
    
    task = RUNNING_TASKS.get(task_id)
    agent_id = task.get('agent_id')
    
    if not agent_id:
        raise HTTPException(status_code=400, detail='Task has no agent assigned')
    
    # Load brain context
    brain = load_brain(config['brain_path'])
    relevant_notes = rank_notes(brain.all_notes, message, top_k=5)
    
    # Build chat prompt
    roster = load_roster()
    agent = roster[agent_id]
    
    system = f"""You are {agent['name']}, {agent['role']}.
Brief: {agent.get('brief', '')}

Respond in your role."""
    
    # Append user message and run Claude
    client = Anthropic()
    response = await client.messages.create(
        model=task.get('model', 'sonnet'),
        system=system,
        messages=[
            {'role': 'user', 'content': message}
        ],
        max_tokens=2048
    )
    
    return {
        'agent_id': agent_id,
        'message': message,
        'response': response.content[0].text
    }
```

---

## Part 5: MCP Tool Manager

### 5.1 Tool Manager (mcp/manager.py)

```python
from langchain_mcp_adapters import MCPAdapter
from typing import List, Dict, Any

class OfficeToolManager:
    """Centralized MCP tool management"""
    
    def __init__(self, config: Dict[str, Any]):
        self.config = config
        self.adapters = {}
        self.tool_cache = {}
    
    async def initialize(self):
        """Load all MCP servers"""
        # For now: manually register known servers
        servers = {
            'gmail': 'mcp://gmail.anthropic.com',
            'slack': 'mcp://slack.anthropic.com',
            'notion': 'mcp://notion.anthropic.com',
            'google_drive': 'mcp://google-drive.anthropic.com',
        }
        
        for name, endpoint in servers.items():
            try:
                adapter = MCPAdapter.from_config({'endpoint': endpoint})
                self.adapters[name] = adapter
            except Exception as e:
                print(f'Warning: Failed to load {name}: {e}')
    
    async def get_tools_for_agent(self, agent_id: str, dept: str) -> List[Dict]:
        """Return callable tools for agent"""
        
        roster = load_roster()
        agent = roster[agent_id]
        
        # Get agent's preferred tools
        tools = []
        for tool_name in agent.get('tools', []):
            if tool_name in self.adapters:
                adapter_tools = await self.adapters[tool_name].get_tools()
                tools.extend(adapter_tools)
        
        # Apply office config (deny list, dept restrictions)
        config_mcp = self.config.get('mcp', {})
        
        if 'deny' in config_mcp:
            tools = [t for t in tools 
                    if t.get('provider') not in config_mcp['deny']]
        
        # Department restrictions
        if 'departments' in config_mcp:
            dept_tools = set()
            for tool_name, depts in config_mcp['departments'].items():
                if dept in depts:
                    dept_tools.add(tool_name)
            tools = [t for t in tools 
                    if t.get('provider') in dept_tools or not dept_tools]
        
        return tools

# Singleton
_tool_manager = None

def get_mcp_tool_manager() -> OfficeToolManager:
    global _tool_manager
    if _tool_manager is None:
        _tool_manager = OfficeToolManager(config)
    return _tool_manager
```

---

## Part 6: Minimal Sandboxing (Subprocess)

### 6.1 Subprocess Executor (sandbox/subprocess.py)

```python
import subprocess
import json
import asyncio
from typing import Dict, Any

class SubprocessToolExecutor:
    """Execute tools in subprocess with timeout/limits"""
    
    async def execute(self, tool_call: Dict, agent_id: str, task_id: str) -> str:
        """Run tool in subprocess, return result"""
        
        # Permission check
        agent = load_roster()[agent_id]
        if tool_call['name'] not in agent.get('tools', []):
            raise PermissionError(f"Agent {agent_id} cannot use {tool_call['name']}")
        
        # Run in subprocess
        try:
            proc = await asyncio.create_subprocess_exec(
                'python', '-m', 'agents_office.tools.executor',
                '--tool', tool_call['name'],
                '--input', json.dumps(tool_call['input']),
                '--agent', agent_id,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE
            )
            
            # Wait with timeout
            stdout, stderr = await asyncio.wait_for(
                proc.communicate(),
                timeout=30
            )
            
            if proc.returncode != 0:
                raise RuntimeError(f'Tool failed: {stderr.decode()}')
            
            return stdout.decode()
            
        except asyncio.TimeoutError:
            raise RuntimeError(f'Tool {tool_call["name"]} exceeded 30s timeout')

# Module entry point: python -m agents_office.tools.executor
if __name__ == '__main__':
    import sys
    import argparse
    
    parser = argparse.ArgumentParser()
    parser.add_argument('--tool')
    parser.add_argument('--input')
    parser.add_argument('--agent')
    args = parser.parse_args()
    
    tool_input = json.loads(args.input)
    
    # Execute the actual tool
    # (Gmail, Slack, Notion, etc.)
    result = execute_tool(args.tool, tool_input, args.agent)
    
    print(json.dumps(result))
```

---

## Part 7: Testing

### 7.1 Test Suite (tests/test_nodes.py)

```python
import pytest
from unittest.mock import AsyncMock, MagicMock, patch

from langgraph.state import OfficeState
from langgraph.nodes import load_context, route_agent, run_agent

@pytest.mark.asyncio
async def test_load_context():
    """Test context loading"""
    state = {
        'task_id': 'test-1',
        'task_text': 'Write a blog post about AI',
        'department': 'marketing',
        'agent_id': None
    }
    
    with patch('langgraph.nodes.load_brain') as mock_brain:
        mock_brain.return_value.all_notes = [
            {'title': 'AI trends', 'content': 'AI is important...'},
        ]
        
        result = await load_context(state)
        
        assert 'relevant_notes' in result
        assert len(result['relevant_notes']) > 0
        assert 'agent_brief' in result

@pytest.mark.asyncio
async def test_route_agent():
    """Test agent routing"""
    state = {
        'task_id': 'test-1',
        'task_text': 'Write a blog post',
        'department': 'marketing',
        'agent_id': None
    }
    
    with patch('langgraph.nodes.Anthropic') as mock_client:
        mock_client.return_value.messages.create.return_value.content = [
            MagicMock(text='{"agent_id": "alice", "reason": "Best for marketing"}')
        ]
        
        result = await route_agent(state)
        
        assert result['agent_id'] == 'alice'
        assert 'reason' in result

@pytest.mark.asyncio
async def test_run_agent():
    """Test agent execution"""
    state = {
        'task_id': 'test-1',
        'task_text': 'Write a blog post',
        'department': 'marketing',
        'agent_id': 'alice',
        'model': 'sonnet',
        'relevant_notes': [],
        'agent_brief': 'Keep it short',
        'skills_summary': '',
        'learned_rules': []
    }
    
    with patch('langgraph.nodes.Anthropic') as mock_client:
        mock_client.return_value.messages.create.return_value.stop_reason = 'end_turn'
        mock_client.return_value.messages.create.return_value.content = [
            MagicMock(text='# AI Trends\n\nAI is transforming...')
        ]
        
        result = await run_agent(state)
        
        assert 'deliverable' in result
        assert len(result['deliverable']) > 0
        assert result['execution_ms'] > 0
```

---

## Quick Start

1. **Clone current repo, add Python layer:**
   ```bash
   cd agents-office
   python3.11 -m venv venv
   pip install -r requirements.txt
   ```

2. **Start with single-agent graph:**
   ```bash
   python main.py
   # FastAPI server at http://localhost:8000
   ```

3. **Test a task:**
   ```bash
   curl -X POST http://localhost:8000/api/tasks \
     -H "Content-Type: application/json" \
     -d '{
       "department": "marketing",
       "text": "Write a Twitter post about our new product",
       "model": "sonnet"
     }'
   ```

4. **Check status:**
   ```bash
   curl http://localhost:8000/api/tasks/abc123
   ```

5. **Extend:** Add teams, routines, sandboxing incrementally.

---

## Production Checklist

- [ ] PostgreSQL checkpointer for state persistence
- [ ] Redis for distributed locking (concurrent routine executions)
- [ ] Docker containers for tool execution
- [ ] Kubernetes CRD for Agent Sandbox
- [ ] Monitoring: Prometheus metrics on graph latency, tool success rate
- [ ] Logging: Structured JSON logs for audit trail
- [ ] Authorization: RBAC for agent capabilities
- [ ] Rate limiting: Per-agent, per-department quotas
