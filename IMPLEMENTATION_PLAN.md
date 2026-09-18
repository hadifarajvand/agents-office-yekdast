# Agents Office v3.6.0-py: Complete Implementation Plan

**Timeline:** 6 weeks | **Team:** 1+ developers | **Status:** Ready to start | **Branch:** develop

---

## Phase Overview

| Phase | Duration | Goal | Key Features |
|-------|----------|------|--------------|
| **Phase 1: Bootstrap** | 1 day | Infrastructure ready | Docker, PostgreSQL, Redis, Jaeger, observability |
| **Phase 2: Core Graph** | Week 1 | Single agent execution | LangGraph StateGraph, 6 nodes, FastAPI routes |
| **Phase 3: Knowledge Base** | Week 1-2 | Agent memory system | Per-agent KB, conversation history, learned rules |
| **Phase 4: Team Execution** | Week 2 | Parallel agents | Team planning, parallel nodes, piece assembly |
| **Phase 5: Routines** | Week 3 | Timetable tasks | RoutineState, scheduling, catch-up logic |
| **Phase 6: Advanced Features** | Week 4 | Learning system | revise:, skills integration, chat endpoint |
| **Phase 7: Sandboxing** | Week 5 | Secure tool execution | Docker executor, permissions, audit logging |
| **Phase 8: Production** | Week 6 | Deploy-ready | PostgreSQL checkpoints, metrics, load testing |

---

# Phase 1: Bootstrap Infrastructure (1 Day)

**Goal:** All services running locally, tests passing, observability visible.

## 1.1 Install Dependencies

```bash
cd D:\Projects\agent-office-yekdast

# Python 3.11+ required
python3.11 -m venv venv
source venv/bin/activate  # or: venv\Scripts\activate

# Core
pip install fastapi uvicorn pydantic anthropic
pip install langgraph langchain langchain-mcp-adapters
pip install psycopg2-binary redis

# Database
pip install sqlalchemy alembic

# Testing
pip install pytest pytest-asyncio pytest-cov

# Observability
pip install opentelemetry-api opentelemetry-sdk opentelemetry-exporter-jaeger
pip install structlog python-json-logger

# Development
pip install black flake8 mypy
pip install docker
```

## 1.2 Backend Structure

Create directory structure:

```
backend/
├── __init__.py
├── main.py                    # FastAPI app
├── config.py                  # Configuration
├── langgraph/
│   ├── __init__.py
│   ├── state.py              # OfficeState, ChatState, RoutineState
│   ├── nodes.py              # 6 core nodes
│   ├── graphs.py             # StateGraph definitions
│   └── edges.py              # Conditional routing
├── api/
│   ├── __init__.py
│   ├── tasks.py              # POST/GET /api/tasks
│   ├── chat.py               # POST /api/tasks/{id}/messages
│   ├── approval.py           # POST /api/tasks/{id}/approve
│   └── routines.py           # Routine endpoints
├── services/
│   ├── __init__.py
│   ├── brain.py              # Load vault notes
│   ├── roster.py             # Load agents
│   ├── skills.py             # Load skills
│   ├── knowledge_base.py     # Agent KB (JSONL + rules)
│   └── learning.py           # Feedback system
├── mcp/
│   ├── __init__.py
│   ├── manager.py            # MCP tool adapter
│   └── executor.py           # Tool execution (scaffold)
├── sandbox/
│   ├── __init__.py
│   └── executor.py           # Sandbox runner (Week 5)
├── observability/
│   ├── __init__.py
│   ├── tracer.py             # Jaeger tracing
│   ├── logger.py             # Structured logging
│   └── metrics.py            # Prometheus metrics
└── tests/
    ├── test_nodes.py         # Node tests
    ├── test_graphs.py        # Graph tests
    ├── test_api.py           # API tests
    └── test_knowledge_base.py
```

## 1.3 Docker Compose Setup

**File: `docker-compose.yml`**

```yaml
version: '3.8'
services:
  backend:
    build:
      context: .
      dockerfile: Dockerfile
    ports:
      - "8000:8000"
    environment:
      ANTHROPIC_API_KEY: ${ANTHROPIC_API_KEY}
      DATABASE_URL: postgresql://ao:aopass@postgres:5432/agents_office
      REDIS_URL: redis://redis:6379
      JAEGER_AGENT_HOST: jaeger
      JAEGER_AGENT_PORT: 6831
    volumes:
      - ./backend:/app/backend
      - ./brain:/app/brain
    depends_on:
      - postgres
      - redis
      - jaeger
    networks:
      - agents-office-net

  postgres:
    image: postgres:15-alpine
    environment:
      POSTGRES_USER: ao
      POSTGRES_PASSWORD: aopass
      POSTGRES_DB: agents_office
    volumes:
      - postgres_data:/var/lib/postgresql/data
    networks:
      - agents-office-net

  redis:
    image: redis:7-alpine
    networks:
      - agents-office-net

  jaeger:
    image: jaegertracing/all-in-one:latest
    ports:
      - "6831:6831/udp"
      - "16686:16686"
    networks:
      - agents-office-net

  prometheus:
    image: prom/prometheus:latest
    ports:
      - "9090:9090"
    volumes:
      - ./observability/prometheus.yml:/etc/prometheus/prometheus.yml
    networks:
      - agents-office-net

volumes:
  postgres_data:

networks:
  agents-office-net:
    driver: bridge
```

## 1.4 Verify Everything Works

```bash
# Start services
docker-compose up -d

# Health check
curl http://localhost:8000/api/health

# View traces
open http://localhost:16686  # Jaeger UI

# View metrics
open http://localhost:9090   # Prometheus
```

**✅ Phase 1 Complete** when Docker services running + health check passes.

---

# Phase 2: Core Graph Implementation (Week 1)

**Goal:** Single agent execution end-to-end (task → Claude → brain).

## 2.1 Define State Schema

**File: `backend/langgraph/state.py`**

Complete state for all features (parallel, routines, approvals):

```python
from typing import TypedDict, Optional, List, Dict, Any
from enum import Enum

class TaskStatus(str, Enum):
    PENDING = "pending"
    IN_PROGRESS = "in_progress"
    WAITING_APPROVAL = "waiting_approval"
    DONE = "done"
    LATE = "late"
    ERROR = "error"

class OfficeState(TypedDict, total=False):
    """Master state for all task types"""
    # Identity
    task_id: str
    department: str
    agent_id: Optional[str]
    created_at: int
    
    # Input
    task_text: str
    model: str
    effort: str
    
    # Context
    relevant_notes: List[Dict]
    agent_brief: str
    skills_summary: str
    learned_rules: List[str]
    kb_history: List[Dict]
    
    # Execution
    status: TaskStatus
    deliverable: Optional[str]
    used_tools: List[str]
    execution_ms: int
    
    # Approval
    needs_outbound_action: bool
    approval_status: Optional[str]
    
    # Team (Week 2)
    is_team_task: bool
    team_pieces: Optional[List[Dict]]
    
    # Routine (Week 3)
    routine_id: Optional[str]
    scheduled_for: Optional[int]
    
    # Metadata
    error: Optional[str]
```

## 2.2 Implement 6 Core Nodes

**File: `backend/langgraph/nodes.py`**

Each node is an async function. Key nodes:

```python
# 1. Load brain context + agent metadata
async def load_context(state: OfficeState) -> Dict:
    # Load brain notes (rank by relevance)
    # Load agent brief, skills, learned rules
    # Load KB conversation history
    return {...updated state...}

# 2. Route to best agent (if not already assigned)
async def route_agent(state: OfficeState) -> Dict:
    # Claude picks agent from roster
    # Or return {} if already assigned
    return {'agent_id': '...', 'routing_reason': '...'}

# 3. Execute agent with Claude + MCP tools
async def run_agent(state: OfficeState) -> Dict:
    # Build system prompt (role + brief + skills + rules)
    # Agentic loop: Claude calls tools → execute → repeat until done
    # Record in knowledge base
    return {'deliverable': '...', 'used_tools': [...], ...}

# 4. Check if approval needed
def check_approval(state: OfficeState) -> str:
    # If deliverable contains send/post/pay/delete → needs approval
    # Otherwise → save directly
    return 'wait_approval' or 'save'

# 5. Wait for human approval (HTTP endpoint sets it)
async def wait_for_approval(state: OfficeState) -> Dict:
    # Poll until /approve or /reject called
    return {'approval_status': 'approved'|'rejected'}

# 6. Save deliverable to brain
async def save_deliverable(state: OfficeState) -> Dict:
    # Write to <brain>/Agents Office/<date>-<agent-id>.md
    # Record used tools, context read, etc.
    return {'saved_at': '...', 'status': 'done'}
```

## 2.3 Build StateGraph

**File: `backend/langgraph/graphs.py`**

```python
from langgraph.graph import StateGraph, START, END

def build_office_graph():
    graph = StateGraph(OfficeState)
    
    # Add nodes
    graph.add_node('load_context', load_context)
    graph.add_node('route', route_agent)
    graph.add_node('run_agent', run_agent)
    graph.add_node('approval_check', check_approval)  # routing only
    graph.add_node('wait_approval', wait_for_approval)
    graph.add_node('save', save_deliverable)
    
    # Linear path
    graph.add_edge(START, 'load_context')
    graph.add_edge('load_context', 'route')
    graph.add_edge('route', 'run_agent')
    graph.add_edge('run_agent', 'approval_check')
    
    # Conditional: approval needed?
    graph.add_conditional_edges(
        'approval_check',
        lambda s: 'wait_approval' if s.get('needs_outbound_action') else 'save'
    )
    
    # Conditional: approved?
    graph.add_conditional_edges(
        'wait_approval',
        lambda s: 'save' if s.get('approval_status') == 'approved' else END
    )
    
    graph.add_edge('save', END)
    
    return graph.compile()
```

## 2.4 FastAPI Routes

**File: `backend/api/tasks.py`**

```python
from fastapi import APIRouter
import uuid
from datetime import datetime
from backend.langgraph.graphs import build_office_graph
from backend.langgraph.state import OfficeState

router = APIRouter(prefix='/api/tasks')
TASKS = {}  # In-memory store (replace with DB later)

@router.post('')
async def create_task(body: dict):
    """POST /api/tasks: Create and execute task"""
    task_id = str(uuid.uuid4())[:8]
    
    state = {
        'task_id': task_id,
        'department': body['department'],
        'task_text': body['text'],
        'model': body.get('model', 'sonnet'),
        'status': 'pending',
        ...
    }
    
    # Execute graph async
    asyncio.create_task(execute_graph(task_id, state))
    return {'task_id': task_id, 'status': 'pending'}

@router.get('/{task_id}')
async def get_task(task_id: str):
    """GET /api/tasks/{task_id}: Get task status"""
    return TASKS.get(task_id, {})

@router.post('/{task_id}/approve')
async def approve(task_id: str):
    """POST /api/tasks/{task_id}/approve"""
    TASKS[task_id]['approval_status'] = 'approved'
    return {'approved': True}

@router.post('/{task_id}/reject')
async def reject(task_id: str, feedback: str):
    """POST /api/tasks/{task_id}/reject"""
    TASKS[task_id]['approval_status'] = 'rejected'
    # Learn from feedback...
    return {'rejected': True}
```

## 2.5 Tests

**File: `backend/tests/test_nodes.py`**

```python
import pytest
from backend.langgraph.nodes import load_context, run_agent

@pytest.mark.asyncio
async def test_load_context():
    state = {'task_id': '1', 'task_text': 'Write post', 'department': 'marketing'}
    result = await load_context(state)
    assert 'relevant_notes' in result

@pytest.mark.asyncio
async def test_run_agent():
    state = {...}  # full state
    result = await run_agent(state)
    assert 'deliverable' in result
```

## 2.6 Verify

```bash
# Start services
docker-compose up -d

# Create task
curl -X POST http://localhost:8000/api/tasks \
  -H "Content-Type: application/json" \
  -d '{"department":"marketing","text":"Write a blog post"}'

# Check status
curl http://localhost:8000/api/tasks/abc123

# View traces
open http://localhost:16686
```

**✅ Phase 2 Complete** when task executes end-to-end with Claude call visible in traces.

---

# Phase 3: Knowledge Base System (Week 1-2)

**Goal:** Each agent remembers conversations, learns from feedback.

## 3.1 Knowledge Base Service

**File: `backend/services/knowledge_base.py`**

```python
import json
from pathlib import Path
from datetime import datetime

class AgentKnowledgeBase:
    """Per-agent memory: conversation history + learned rules"""
    
    def __init__(self, agent_id: str):
        self.agent_id = agent_id
        self.kb_dir = Path(f'./brain/Agents Office/kb/{agent_id}')
        self.kb_dir.mkdir(parents=True, exist_ok=True)
        
        self.history_file = self.kb_dir / 'history.jsonl'
        self.rules_file = self.kb_dir / 'rules.md'
    
    async def add_conversation(self, task_id: str, role: str, content: str):
        """Store conversation turn (immutable append)"""
        entry = {
            'timestamp': datetime.now().isoformat(),
            'task_id': task_id,
            'role': role,
            'content': content
        }
        with open(self.history_file, 'a') as f:
            f.write(json.dumps(entry) + '\n')
    
    async def get_history(self, task_id: str, limit: int = 20) -> List[Dict]:
        """Retrieve conversation history for context"""
        if not self.history_file.exists():
            return []
        
        lines = self.history_file.read_text().strip().split('\n')
        entries = [json.loads(line) for line in lines if line]
        
        if task_id:
            entries = [e for e in entries if e['task_id'] == task_id]
        
        return entries[-limit:]
    
    async def add_rule(self, rule: str, source_task: str, feedback: str):
        """Record standing rule from feedback"""
        entry = f"- {rule} ← {source_task}: {feedback}\n"
        with open(self.rules_file, 'a') as f:
            f.write(entry)
    
    async def get_rules(self) -> List[str]:
        """Return learned rules for prompt"""
        if not self.rules_file.exists():
            return []
        
        lines = self.rules_file.read_text().split('\n')
        return [line.strip('- ').split(' ← ')[0] for line in lines if line.startswith('- ')]
```

## 3.2 Integrate KB into Nodes

Update `run_agent` node to:
1. Load KB history for context
2. Store conversation after execution
3. Load learned rules into system prompt

```python
async def run_agent(state):
    kb = AgentKnowledgeBase(state['agent_id'])
    
    # Load history
    history = await kb.get_history(state['task_id'], limit=20)
    learned_rules = await kb.get_rules()
    
    # Use in prompt...
    
    # After execution, store conversation
    await kb.add_conversation(state['task_id'], 'user', state['task_text'])
    await kb.add_conversation(state['task_id'], 'assistant', deliverable)
    
    return {...}
```

## 3.3 Learning from Feedback

Update rejection endpoint to learn:

```python
@router.post('/{task_id}/reject')
async def reject(task_id: str, feedback: str):
    task = TASKS[task_id]
    kb = AgentKnowledgeBase(task['agent_id'])
    
    # Store as learned rule
    await kb.add_rule(
        f"In similar tasks, avoid: {feedback[:50]}",
        task_id,
        feedback
    )
    
    return {'rejected': True}
```

**✅ Phase 3 Complete** when learned rules appear in subsequent tasks.

---

# Phase 4: Team Execution (Week 2)

**Goal:** Lead splits work → parallel teammates → merged result.

## 4.1 Add Team State

Update `OfficeState`:
```python
is_team_task: bool
team_lead_id: Optional[str]
team_pieces: Optional[List[Dict]]  # [{agent_id, subtask, result}]
team_notes: Optional[List[Dict]]   # notes between teammates
```

## 4.2 Implement Team Nodes

Add 3 new nodes:

```python
async def team_plan(state):
    """Lead splits task into pieces for teammates"""
    lead = load_roster()[state['agent_id']]
    
    prompt = f"Split this task into 2-4 pieces for your team: {state['task_text']}"
    
    # Claude plans pieces
    response = await claude_call(prompt)
    pieces = parse_json(response)
    
    return {'team_pieces': pieces}

async def team_execute(state):
    """Run teammates in parallel"""
    pieces = state['team_pieces']
    
    async def run_piece(piece):
        # Each teammate gets own state + context
        return await run_agent({**state, 'task_id': piece['agent_id'], ...})
    
    results = await asyncio.gather(*[run_piece(p) for p in pieces])
    
    return {'team_pieces': results}

async def team_merge(state):
    """Lead combines pieces into final deliverable"""
    pieces = state['team_pieces']
    
    prompt = f"Combine these pieces into one deliverable: {format_pieces(pieces)}"
    
    response = await claude_call(prompt)
    
    return {'deliverable': response, 'is_team_task': True}
```

## 4.3 Update Graph

Insert team nodes before run_agent:

```python
def route_agent_or_team(state):
    return 'team_plan' if state.get('is_team_task') else 'run_agent'

graph.add_conditional_edges('route', route_agent_or_team)

graph.add_edge('team_plan', 'team_execute')
graph.add_edge('team_execute', 'team_merge')
graph.add_edge('team_merge', 'approval_check')

graph.add_edge('run_agent', 'approval_check')
```

**✅ Phase 4 Complete** when team tasks execute parallel + lead merges results.

---

# Phase 5: Routines & Scheduling (Week 3)

**Goal:** Timetable-driven tasks (every weekday at 9am, etc.).

## 5.1 Routine State & Graph

**File: `backend/langgraph/routines.py`**

Create separate `RoutineState` graph with scheduler:

```python
class RoutineState(TypedDict, total=False):
    routine_id: str
    department: str
    agent_id: str
    when: Dict  # {kind: "weekly", days: [1,4], at: "09:00"}
    next_run_at: int
    last_run_at: Optional[int]
    is_late: bool  # running after downtime

def build_routine_graph():
    """Separate graph for timetable-driven execution"""
    graph = StateGraph(RoutineState)
    
    graph.add_node('check_schedule', check_routine_schedule)
    graph.add_node('setup_task', setup_routine_task)
    graph.add_node('execute', run_agent)  # reuse
    graph.add_node('record_run', record_routine_run)
    graph.add_node('schedule_next', schedule_next_run)
    
    # Linear flow
    graph.add_edge(START, 'check_schedule')
    graph.add_conditional_edges('check_schedule', 
        lambda s: 'setup_task' if s['status'] == 'active' else END)
    graph.add_edge('setup_task', 'execute')
    graph.add_edge('execute', 'record_run')
    graph.add_edge('record_run', 'schedule_next')
    graph.add_edge('schedule_next', END)
    
    return graph.compile()
```

## 5.2 Server-Side Clock

**File: `backend/services/scheduler.py`**

```python
import asyncio
from datetime import datetime
from backend.services.brain import load_brain

async def routine_clock():
    """Server-side clock: check routines every minute"""
    while True:
        await asyncio.sleep(60)  # Check every minute
        
        brain = load_brain()
        routines = brain.get('routines.json', [])
        
        for routine in routines:
            if should_run(routine):
                # Fire routine execution
                await execute_routine(routine)
                record_run(routine)
```

## 5.3 Approval for Outbound Actions

Routines with send/post/pay need approval by default:

```python
routine['needsOk'] = True  # default
# → Task lands in WAITING ON APPROVAL
# → User clicks APPROVE, then agent sends
```

**✅ Phase 5 Complete** when routines fire on schedule + support catch-up.

---

# Phase 6: Advanced Features (Week 4)

## 6.1 Skills Integration

**File: `backend/services/skills.py`**

Load skill files from `<brain>/Agents Office/skills/<name>/SKILL.md`:

```python
def load_skills_for_agent(agent_id: str):
    """Load all skills bound to this agent"""
    skills_dir = Path('./brain/Agents Office/skills')
    
    skills = []
    for skill_dir in skills_dir.iterdir():
        skill_md = skill_dir / 'SKILL.md'
        if skill_md.exists():
            front_matter = parse_yaml_front_matter(skill_md)
            if agent_id in front_matter.get('agents', []):
                skills.append({
                    'name': front_matter['name'],
                    'description': skill_md.read_text(),
                    'template': (skill_dir / 'template.md').read_text()
                })
    
    return skills
```

## 6.2 Chat Endpoint

**File: `backend/api/chat.py`**

```python
@router.post('/tasks/{task_id}/messages')
async def send_message(task_id: str, message: str):
    """Chat with agent in their persona"""
    task = TASKS[task_id]
    agent_id = task['agent_id']
    agent = load_roster()[agent_id]
    
    system = f"""You are {agent['name']}, {agent['role']}.
Brief: {agent.get('brief', '')}"""
    
    response = await claude_call(system, message)
    
    # Store in KB
    kb = AgentKnowledgeBase(agent_id)
    await kb.add_conversation(task_id, 'user', message)
    await kb.add_conversation(task_id, 'assistant', response)
    
    return {'response': response}
```

## 6.3 Brain Graph Rebuild

**File: `backend/services/brain.py`**

After saving deliverable, rebuild wiki-link graph:

```python
async def rebuild_brain_graph():
    """Rebuild graph after new notes written"""
    # Read all .md files in brain
    # Extract [[wiki-link]] references
    # Output graph visualization
    pass
```

**✅ Phase 6 Complete** when skills load, chat works, graph updates.

---

# Phase 7: Sandboxing (Week 5)

**Goal:** Tool execution in isolated Docker containers.

## 7.1 Docker Sandbox Executor

**File: `backend/sandbox/executor.py`**

```python
import docker
import json

class SandboxedToolExecutor:
    """Execute MCP tool calls in Docker container"""
    
    def __init__(self):
        self.client = docker.from_env()
        self.image = 'agents-office-sandbox:latest'
    
    async def execute(self, tool_call: dict, agent_id: str) -> str:
        """Run tool in container with 30s timeout"""
        
        # Permission check
        agent = load_roster()[agent_id]
        if tool_call['tool'] not in agent.get('tools', []):
            raise PermissionError(f"{agent_id} cannot use {tool_call['tool']}")
        
        # Run in container
        container = self.client.containers.run(
            self.image,
            ['--tool', tool_call['tool'],
             '--input', json.dumps(tool_call.get('input', {})),
             '--agent', agent_id],
            mem_limit='256m',
            cpus='1.0',
            timeout=30,
            remove=True
        )
        
        return container.output.decode()
```

## 7.2 Audit Logging

**File: `backend/observability/audit.py`**

```python
async def log_tool_call(tool_name, agent_id, task_id, success, error=None):
    """Immutable audit trail"""
    entry = {
        'timestamp': datetime.now().isoformat(),
        'tool': tool_name,
        'agent': agent_id,
        'task': task_id,
        'success': success,
        'error': error
    }
    
    # Write to immutable log
    audit_file = Path(f'./logs/audit/{task_id}.jsonl')
    audit_file.parent.mkdir(parents=True, exist_ok=True)
    
    with open(audit_file, 'a') as f:
        f.write(json.dumps(entry) + '\n')
```

## 7.3 Permission Whitelist

**File: `backend/mcp/whitelist.py`**

```python
ALLOWED_TOOLS = {
    'alice': ['Gmail', 'Notion'],
    'bob': ['Slack', 'Gmail'],
    'default': ['web']  # web search always available
}

def can_tool_call(agent_id: str, tool: str) -> bool:
    allowed = ALLOWED_TOOLS.get(agent_id, ALLOWED_TOOLS['default'])
    return tool in allowed
```

**✅ Phase 7 Complete** when tool calls execute in isolated containers + audit trail written.

---

# Phase 8: Production Ready (Week 6)

## 8.1 PostgreSQL Checkpointing

Use LangGraph checkpointer for state recovery:

```python
from langgraph.checkpoint.postgres import PostgresCheckpointer

checkpointer = PostgresCheckpointer(conn=postgres_connection)
graph = graph.compile(checkpointer=checkpointer)

# Now state survives crashes → can resume execution
```

## 8.2 Redis Caching

Cache agent rosters, skills, brain index:

```python
redis_client = redis.from_url(REDIS_URL)

@lru_cache(maxsize=1)
def load_roster_cached():
    cached = redis_client.get('roster')
    if cached:
        return json.loads(cached)
    
    roster = load_roster()
    redis_client.set('roster', json.dumps(roster), ex=3600)
    return roster
```

## 8.3 Metrics & Monitoring

Prometheus metrics:

```python
from prometheus_client import Counter, Histogram

task_counter = Counter('ao_tasks_total', 'Total tasks', ['department', 'status'])
execution_time = Histogram('ao_execution_ms', 'Task execution time', ['department'])
tool_calls = Counter('ao_tool_calls_total', 'Tool calls', ['tool', 'success'])

# In nodes:
task_counter.labels(department=state['department'], status='done').inc()
execution_time.labels(department=state['department']).observe(duration_ms)
```

## 8.4 Load Testing

```bash
# Create 100 tasks
for i in {1..100}; do
  curl -X POST http://localhost:8000/api/tasks \
    -d '{"department":"marketing","text":"Task $i"}'
done

# Monitor
open http://localhost:9090  # Prometheus
```

**✅ Phase 8 Complete** when production-ready: metrics visible, no data loss on restart.

---

# Git Workflow (All Phases)

## Branch Strategy

```
develop (integration)
  ↑
feature/core-graph (Week 1)
feature/team-execution (Week 2)
feature/routines (Week 3)
feature/sandboxing (Week 5)
```

## Committing Code

```bash
# Create feature branch
git checkout -b feature/langgraph-core-implementation

# Code → commit → test → push
git add backend/langgraph/state.py
git commit -m "feat(langgraph): add OfficeState schema

- Define state for all task types (single, team, routine)
- Support approval workflow, knowledge base, metadata

Co-Authored-By: Claude Haiku 4.5 <noreply@anthropic.com>"

# Pre-commit hooks auto-test before allowing commit
# Black formatter ✓
# Flake8 linting ✓
# Mypy type check ✓
# Pytest ✓

git push origin feature/langgraph-core-implementation
```

## Pull Request → Merge

```bash
# On GitHub: Create PR
# Requires: 1 reviewer + all tests passing

# After approval & merge
git checkout develop
git pull origin develop
git branch -d feature/langgraph-core-implementation
```

---

# Testing Strategy

| Phase | Test Types | Coverage | Acceptance |
|-------|-----------|----------|-----------|
| 1 | Docker health | N/A | Services running |
| 2 | Unit (nodes), API (routes), E2E (task) | 80%+ | Single task end-to-end |
| 3 | KB (storage, retrieval), Learning (rules) | 85%+ | Learned rules appear next task |
| 4 | Team (planning, parallel, merge) | 80%+ | Parallel execution faster than serial |
| 5 | Scheduler (timing, catch-up), Approval | 85%+ | Routine fires at right time |
| 6 | Chat (persona), Skills (loading) | 80%+ | Chat matches agent role |
| 7 | Sandbox (isolation, timeout, audit) | 90%+ | Container escape fails safely |
| 8 | Load (100 concurrent), Recovery (restart) | Integration | No data loss on restart |

**Run:**
```bash
pytest backend/tests -v --cov=backend
```

---

# Success Criteria

| Phase | Criterion |
|-------|-----------|
| 1 | Docker services healthy, `curl /api/health` returns 200 |
| 2 | Task executes: POST /api/tasks → Claude call → saves to brain |
| 3 | Learned rules persist: revise: → rule appears in next task prompt |
| 4 | Team task runs 2-4 teammates in parallel, lead merges results |
| 5 | Routine fires at scheduled time, catches up if office was offline |
| 6 | Agent chats in persona, skills loaded, graph rebuilt |
| 7 | Tool call sandboxed in container, audit logged, escape prevented |
| 8 | Metrics visible in Prometheus, state persists after restart |

---

# Common Issues & Solutions

| Issue | Solution |
|-------|----------|
| Pre-commit hook fails | Run `black backend/`, fix errors, retry commit |
| Tests fail locally but pass CI | Likely DB state issue; `docker-compose down -v` to reset |
| Claude calls failing | Check `ANTHROPIC_API_KEY` env var, OpenAI SDK version |
| Traces not showing | Check Jaeger running: `docker-compose logs jaeger` |
| Brain notes not loading | Check path: `./brain/` vs absolute path |
| Team execution not parallel | Verify `asyncio.gather()` used, not sequential await |
| Routine not firing | Check scheduler running, time zone correct, `next_run_at` > now |
| Docker sandbox container crashes | Check memory limit 256MB sufficient, or increase in compose |

---

# Files Reference

**Core implementation:**
- `backend/langgraph/state.py` → OfficeState schema
- `backend/langgraph/nodes.py` → 6 core nodes
- `backend/langgraph/graphs.py` → StateGraph
- `backend/api/tasks.py` → FastAPI routes

**Support:**
- `backend/services/knowledge_base.py` → Agent KB
- `backend/services/brain.py` → Brain loader
- `backend/services/roster.py` → Agent loader
- `backend/services/skills.py` → Skills loader
- `backend/observability/tracer.py` → Tracing

**Testing:**
- `backend/tests/test_nodes.py` → Node tests
- `backend/tests/test_api.py` → API tests
- `backend/tests/test_knowledge_base.py` → KB tests

---

# Timeline Estimate

| Phase | Duration | Effort | Notes |
|-------|----------|--------|-------|
| 1 | 1 day | 2h | Setup only, mostly config |
| 2 | 3-4 days | 12h | Core logic, requires Claude knowledge |
| 3 | 2 days | 8h | Straightforward storage layer |
| 4 | 3 days | 12h | Parallel execution complexity |
| 5 | 2 days | 8h | Scheduler + state management |
| 6 | 2 days | 8h | Integration of existing pieces |
| 7 | 3 days | 12h | Docker + security best practices |
| 8 | 2 days | 8h | Production hardening |
| **Total** | **6 weeks** | **68h** | Can be done 1-2 devs full-time |

---

# Next Steps

1. **Right now:** Read `QUICK_REFERENCE.md` (this guide summary)
2. **Today:** Complete Phase 1 (Bootstrap)
3. **This week:** Complete Phase 2 (Core Graph)
4. **Next week:** Continue with Phases 3-4
5. **Weekly:** Commit progress, run tests, update traces

**Ready?** Start with Phase 1 → docker-compose up -d
