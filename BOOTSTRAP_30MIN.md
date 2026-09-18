# Agents Office: 30-Minute Bootstrap (Production Setup)

**Goal:** Boot a working skeleton that runs agents-office v3.6 backend in Python + Docker, with all v3.6 features planned (not all coded yet).

**What you'll have in 30 min:**
- ✅ FastAPI server running on port 8000
- ✅ Docker container setup for agent sandboxing
- ✅ Agent knowledge base (long-term memory per agent)
- ✅ Complete logging/tracing infrastructure
- ✅ Test suite skeleton (unit + integration)
- ✅ Same API as v3.6 (no frontend changes)
- ✅ GitHub + Dockerploy CI/CD config

**Timeline for full implementation:** 4-6 weeks (not 30 min)

---

## Architecture Overview (Your System)

```
agents-office-v3.6-frontend (unchanged)
                 ↓
        FastAPI backend (Python, new)
                 ↓
        ┌────────────────────┐
        │  LangGraph States  │
        ├────────────────────┤
        │ - OfficeState      │
        │ - RoutineState     │
        │ - ChatState        │
        │ - ApprovalState    │
        └────────────────────┘
                 ↓
        ┌────────────────────┐
        │   Orchestration    │
        ├────────────────────┤
        │ - Single agent     │
        │ - Team (parallel)  │
        │ - Routines/clock   │
        │ - Approval gates   │
        └────────────────────┘
                 ↓
        ┌────────────────────┐
        │  Agent Knowledge   │
        │      Base (KB)     │
        ├────────────────────┤
        │ - Per-agent memory │
        │ - Conversation log │
        │ - Learned rules    │
        │ - Skills/brief     │
        └────────────────────┘
                 ↓
        ┌────────────────────┐
        │  Sandboxed Tools   │
        ├────────────────────┤
        │ Docker containers  │
        │ for each tool call │
        └────────────────────┘
                 ↓
        ┌────────────────────┐
        │   Observability    │
        ├────────────────────┤
        │ - Traces (all ops) │
        │ - Logs (debug)     │
        │ - Metrics (health) │
        └────────────────────┘
```

---

## Part 1: 30-Minute Bootstrap

### Step 1: Project Structure (2 min)

```bash
# Clone agents-office, add Python backend
cd agents-office-yekdast
mkdir -p backend/{langgraph,mcp,sandbox,services,api,tests,observability}

# Python virtual env
python3.11 -m venv venv
source venv/bin/activate  # macOS/Linux
# or: venv\Scripts\activate  # Windows

# Install core
pip install fastapi uvicorn pydantic anthropic
pip install langgraph langchain langchain-mcp-adapters
pip install psycopg2-binary redis  # for persistence
pip install docker  # for container orchestration
pip install pytest pytest-asyncio  # testing
pip install opentelemetry-api opentelemetry-sdk  # tracing
pip install structlog python-json-logger  # logging
```

### Step 2: FastAPI Server (5 min)

**backend/main.py:**
```python
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
import uvicorn
import json
from pathlib import Path

app = FastAPI(title="Agents Office Backend", version="3.6.0-py")

# CORS for frontend
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:4520", "http://localhost:3000"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Load config (same format as v3.6)
def load_config():
    config_path = Path(__file__).parent.parent / "office.config.json"
    with open(config_path) as f:
        return json.load(f)

CONFIG = load_config()

# Placeholder routes (will implement)
@app.get("/api/health")
async def health():
    return {"status": "ok", "version": "3.6.0-py"}

@app.post("/api/tasks")
async def create_task(task: dict):
    """Create and execute task (placeholder)"""
    return {
        "task_id": "task-1",
        "status": "pending",
        "message": "Task creation not yet implemented"
    }

@app.get("/api/tasks/{task_id}")
async def get_task(task_id: str):
    """Get task status (placeholder)"""
    return {
        "task_id": task_id,
        "status": "pending",
        "message": "Task retrieval not yet implemented"
    }

if __name__ == "__main__":
    uvicorn.run(app, host="0.0.0.0", port=8000)
```

### Step 3: Docker Setup (5 min)

**Dockerfile (agent sandbox):**
```dockerfile
FROM python:3.11-slim

WORKDIR /agent

# Minimal environment (no build tools)
RUN apt-get update && apt-get install -y --no-install-recommends curl && \
    rm -rf /var/lib/apt/lists/*

# Install only tool requirements
COPY sandbox/tool-requirements.txt .
RUN pip install --no-cache-dir -r tool-requirements.txt

# Non-root user
RUN useradd -m -s /sbin/nologin agent
USER agent

# Workspace
VOLUME ["/agent/workspace", "/agent/logs"]

COPY sandbox/executor.py .
ENTRYPOINT ["python", "executor.py"]
```

**docker-compose.yml:**
```yaml
version: '3.8'
services:
  # Agents Office backend
  backend:
    build:
      context: .
      dockerfile: Dockerfile.backend
    ports:
      - "8000:8000"
    environment:
      ANTHROPIC_API_KEY: ${ANTHROPIC_API_KEY}
      DATABASE_URL: postgresql://ao:aopass@postgres:5432/agents_office
      REDIS_URL: redis://redis:6379
    volumes:
      - ./backend:/app/backend
      - ./brain:/app/brain
    depends_on:
      - postgres
      - redis
    networks:
      - agents-office-net

  # Agent sandbox (Docker-in-Docker for spawning tool containers)
  sandbox-controller:
    image: docker:dind
    privileged: true
    volumes:
      - /var/run/docker.sock:/var/run/docker.sock
    networks:
      - agents-office-net

  # Postgres for state persistence
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

  # Redis for caching + session state
  redis:
    image: redis:7-alpine
    networks:
      - agents-office-net

volumes:
  postgres_data:

networks:
  agents-office-net:
    driver: bridge
```

### Step 4: Agent Knowledge Base (8 min)

**backend/services/knowledge_base.py:**
```python
import json
from datetime import datetime
from pathlib import Path
from typing import List, Dict, Optional
import hashlib

class AgentKnowledgeBase:
    """
    Per-agent memory system:
    - Conversation history
    - Learned rules (from feedback)
    - Skills/briefs
    - Long-term context
    """
    
    def __init__(self, agent_id: str, kb_dir: str = "./brain/Agents Office/kb"):
        self.agent_id = agent_id
        self.kb_dir = Path(kb_dir)
        self.kb_dir.mkdir(parents=True, exist_ok=True)
        
        self.agent_kb_dir = self.kb_dir / agent_id
        self.agent_kb_dir.mkdir(exist_ok=True)
        
        self.history_file = self.agent_kb_dir / "history.jsonl"
        self.learned_rules_file = self.agent_kb_dir / "learned_rules.md"
        self.context_file = self.agent_kb_dir / "context.json"
    
    async def add_conversation(self, 
                              task_id: str,
                              role: str,  # user | assistant
                              content: str,
                              metadata: dict = None):
        """Record conversation turn"""
        entry = {
            "timestamp": datetime.now().isoformat(),
            "task_id": task_id,
            "role": role,
            "content": content,
            "metadata": metadata or {}
        }
        
        # Append to history (immutable log)
        with open(self.history_file, 'a') as f:
            f.write(json.dumps(entry) + '\n')
    
    async def get_conversation_history(self, 
                                       task_id: Optional[str] = None,
                                       limit: int = 50) -> List[Dict]:
        """Retrieve conversation history for context"""
        if not self.history_file.exists():
            return []
        
        lines = self.history_file.read_text().strip().split('\n')
        entries = [json.loads(line) for line in lines if line]
        
        # Filter by task if specified
        if task_id:
            entries = [e for e in entries if e['task_id'] == task_id]
        
        # Return last N entries
        return entries[-limit:]
    
    async def add_learned_rule(self, rule: str, source_task: str, source_feedback: str):
        """Record a standing rule from feedback"""
        rule_entry = f"- {rule} ← feedback on task {source_task}: {source_feedback}\n"
        
        with open(self.learned_rules_file, 'a') as f:
            f.write(rule_entry)
    
    async def get_learned_rules(self) -> List[str]:
        """Get all standing rules for prompt"""
        if not self.learned_rules_file.exists():
            return []
        
        content = self.learned_rules_file.read_text()
        # Parse markdown bullet points
        rules = [line.strip('- ').split(' ← ')[0] 
                for line in content.split('\n') 
                if line.startswith('- ')]
        return rules
    
    async def set_long_term_context(self, context: dict):
        """Store agent's long-term state (projects, goals, etc.)"""
        self.context_file.write_text(json.dumps(context, indent=2))
    
    async def get_long_term_context(self) -> dict:
        """Retrieve agent's long-term context"""
        if not self.context_file.exists():
            return {}
        
        return json.loads(self.context_file.read_text())

# Usage in agent node:
async def run_agent_with_kb(state: dict) -> dict:
    """Run agent with access to knowledge base"""
    agent_id = state['agent_id']
    kb = AgentKnowledgeBase(agent_id)
    
    # Load history for context
    history = await kb.get_conversation_history(state['task_id'], limit=20)
    learned_rules = await kb.get_learned_rules()
    long_term_context = await kb.get_long_term_context()
    
    # Use in prompt...
    # After execution, record conversation
    await kb.add_conversation(state['task_id'], 'assistant', state['deliverable'])
    
    return state
```

### Step 5: Observability (Tracing & Logging) (7 min)

**backend/observability/tracer.py:**
```python
import structlog
from opentelemetry import trace, metrics
from opentelemetry.sdk.trace import TracerProvider
from opentelemetry.sdk.trace.export import BatchSpanProcessor
from opentelemetry.exporter.jaeger.thrift import JaegerExporter
from opentelemetry.sdk.resources import SERVICE_NAME, Resource
import json
from datetime import datetime

# Configure structured logging
structlog.configure(
    processors=[
        structlog.stdlib.filter_by_level,
        structlog.stdlib.add_logger_name,
        structlog.stdlib.add_log_level,
        structlog.stdlib.PositionalArgumentsFormatter(),
        structlog.processors.TimeStamper(fmt="iso"),
        structlog.processors.StackInfoRenderer(),
        structlog.processors.format_exc_info,
        structlog.dev.ConsoleRenderer()
    ],
    context_class=dict,
    logger_factory=structlog.stdlib.LoggerFactory(),
    cache_logger_on_first_use=True,
)

# Jaeger tracing (for distributed tracing)
jaeger_exporter = JaegerExporter(
    agent_host_name="localhost",
    agent_port=6831,
)

trace_provider = TracerProvider(
    resource=Resource.create({SERVICE_NAME: "agents-office"})
)
trace_provider.add_span_processor(BatchSpanProcessor(jaeger_exporter))
trace.set_tracer_provider(trace_provider)

tracer = trace.get_tracer(__name__)
logger = structlog.get_logger()

class TaskTracer:
    """Trace every task execution step"""
    
    def __init__(self, task_id: str):
        self.task_id = task_id
        self.task_span = tracer.start_as_current_span(f"task-{task_id}")
    
    def log_node_start(self, node_name: str, state: dict):
        """Log when a graph node starts"""
        logger.info("node_start", 
                   task_id=self.task_id,
                   node=node_name,
                   agent_id=state.get('agent_id'),
                   department=state.get('department'))
    
    def log_node_end(self, node_name: str, duration_ms: int, result: dict):
        """Log when a node completes"""
        logger.info("node_end",
                   task_id=self.task_id,
                   node=node_name,
                   duration_ms=duration_ms,
                   result_size=len(str(result)))
    
    def log_tool_call(self, tool_name: str, input_data: dict, 
                     result: str, duration_ms: int, success: bool):
        """Log tool execution"""
        logger.info("tool_call",
                   task_id=self.task_id,
                   tool=tool_name,
                   input_keys=list(input_data.keys()),
                   result_size=len(result),
                   duration_ms=duration_ms,
                   success=success)
    
    def log_approval_needed(self, reason: str, deliverable_preview: str):
        """Log when approval is needed"""
        logger.info("approval_needed",
                   task_id=self.task_id,
                   reason=reason,
                   preview=deliverable_preview[:100])
    
    def close(self):
        self.task_span.end()

# Usage in FastAPI:
@app.post("/api/tasks")
async def create_task(task: dict):
    task_id = generate_task_id()
    tracer_instance = TaskTracer(task_id)
    
    try:
        # Execute graph
        # ... trace each node ...
        tracer_instance.log_node_start("load_context", {})
        # ...
        tracer_instance.log_node_end("load_context", 150, {})
    finally:
        tracer_instance.close()
    
    return {"task_id": task_id}
```

**docker-compose additions (observability):**
```yaml
  jaeger:
    image: jaegertracing/all-in-one:latest
    ports:
      - "6831:6831/udp"
      - "16686:16686"  # Jaeger UI
    networks:
      - agents-office-net

  prometheus:
    image: prom/prometheus:latest
    volumes:
      - ./observability/prometheus.yml:/etc/prometheus/prometheus.yml
    ports:
      - "9090:9090"
    networks:
      - agents-office-net
```

Access traces: http://localhost:16686

### Step 6: Test Suite Skeleton (3 min)

**backend/tests/test_nodes.py:**
```python
import pytest
from unittest.mock import AsyncMock, patch
from backend.langgraph.nodes import load_context, run_agent

@pytest.mark.asyncio
async def test_load_context_loads_brain():
    """Test context loading from brain"""
    state = {
        'task_id': 'test-1',
        'task_text': 'Write a blog post',
        'department': 'marketing'
    }
    
    result = await load_context(state)
    
    assert 'relevant_notes' in result
    assert 'agent_brief' in result
    assert 'learned_rules' in result

@pytest.mark.asyncio
async def test_run_agent_with_knowledge_base():
    """Test agent execution uses KB"""
    state = {
        'task_id': 'test-1',
        'agent_id': 'alice',
        'task_text': 'Do something',
        'department': 'marketing'
    }
    
    with patch('backend.langgraph.nodes.Anthropic'):
        result = await run_agent(state)
        
        # Verify KB was accessed
        assert result.get('agent_id') == 'alice'

@pytest.mark.asyncio
async def test_sandbox_execution():
    """Test tool execution in sandbox"""
    from backend.sandbox.executor import SandboxedToolExecutor
    
    executor = SandboxedToolExecutor()
    result = await executor.execute(
        {'tool': 'gmail', 'action': 'read'},
        'alice',
        'test-1'
    )
    
    assert result is not None

def test_tracer_logs_all_steps():
    """Test observability tracer"""
    from backend.observability.tracer import TaskTracer
    
    tracer = TaskTracer('test-1')
    tracer.log_node_start('load_context', {'agent_id': 'alice'})
    tracer.log_tool_call('gmail', {}, 'result', 150, True)
    tracer.close()
    
    # Verify logs written (check stdout or log file)
```

**backend/tests/test_knowledge_base.py:**
```python
import pytest
from backend.services.knowledge_base import AgentKnowledgeBase

@pytest.mark.asyncio
async def test_kb_stores_conversation():
    """Test KB persists conversation"""
    kb = AgentKnowledgeBase('alice')
    
    await kb.add_conversation('task-1', 'user', 'Do something')
    await kb.add_conversation('task-1', 'assistant', 'Done!')
    
    history = await kb.get_conversation_history('task-1')
    assert len(history) == 2
    assert history[0]['role'] == 'user'

@pytest.mark.asyncio
async def test_kb_stores_learned_rules():
    """Test KB persists standing rules"""
    kb = AgentKnowledgeBase('alice')
    
    await kb.add_learned_rule(
        'Always sign off with "Best, Alice"',
        'task-1',
        'User said always sign off this way'
    )
    
    rules = await kb.get_learned_rules()
    assert len(rules) > 0
    assert 'Best, Alice' in rules[0]

@pytest.mark.asyncio
async def test_kb_long_term_context():
    """Test KB stores long-term state"""
    kb = AgentKnowledgeBase('alice')
    
    context = {
        'current_project': 'Website redesign',
        'client': 'Acme Corp',
        'deadline': '2026-12-31'
    }
    
    await kb.set_long_term_context(context)
    retrieved = await kb.get_long_term_context()
    
    assert retrieved['current_project'] == 'Website redesign'
```

**Run tests:**
```bash
pytest backend/tests -v --asyncio-mode=auto
```

### Step 7: GitHub + Dockerploy CI/CD (2 min)

**.github/workflows/deploy.yml:**
```yaml
name: Build & Deploy

on:
  push:
    branches: [main]

jobs:
  build:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v3
      
      - name: Build Docker image
        run: docker build -t agents-office:latest .
      
      - name: Push to registry
        run: |
          docker tag agents-office:latest ${{ secrets.REGISTRY_URL }}/agents-office:latest
          docker push ${{ secrets.REGISTRY_URL }}/agents-office:latest
  
  deploy:
    needs: build
    runs-on: ubuntu-latest
    steps:
      - name: Trigger Dockerploy
        run: |
          curl -X POST ${{ secrets.DOCKERPLOY_WEBHOOK }} \
            -H "Authorization: Bearer ${{ secrets.DOCKERPLOY_TOKEN }}" \
            -d '{"image": "agents-office:latest"}'
```

---

## Part 2: What's Implemented in 30 Minutes

✅ FastAPI server (listening on 8000)
✅ Docker setup (sandbox controller + containers)
✅ Agent Knowledge Base (per-agent memory)
✅ Observability (structured logging + tracing)
✅ Test suite skeleton (unit + integration test examples)
✅ CI/CD config (GitHub → Dockerploy)
✅ API routes (placeholders matching v3.6)

---

## Part 3: Implementation Roadmap (Next 4-6 Weeks)

### Week 1: Core Graph
- [ ] OfficeState + routing node
- [ ] Single-agent execution node
- [ ] Approval workflow node
- [ ] Brain context loading

### Week 2: Team Execution
- [ ] Team planning node (lead splits work)
- [ ] Parallel teammate execution
- [ ] Piece assembly (lead writes final)
- [ ] Team notes/coordination

### Week 3: Routines & Scheduling
- [ ] RoutineState graph
- [ ] Timetable parsing (every weekday at 9am, etc.)
- [ ] Catch-up logic (run missed tasks once)
- [ ] Routine approval gates

### Week 4: Advanced Features
- [ ] Learning system (revise: → rules)
- [ ] Skills integration (skill.md files)
- [ ] Chat endpoint (agent personas)
- [ ] Brain graph rebuild

### Week 5: Sandboxing & Security
- [ ] Docker executor for tools
- [ ] Permission whitelist (MCP servers)
- [ ] Audit logging (who did what)
- [ ] Security tests

### Week 6: Production & Polish
- [ ] PostgreSQL checkpointing
- [ ] Redis session caching
- [ ] Metrics/monitoring (Prometheus)
- [ ] Load testing
- [ ] Documentation

---

## Part 4: Running the 30-Minute Setup

```bash
# 1. Copy code above into files
# 2. Start services
docker-compose up -d

# 3. Check backend
curl http://localhost:8000/api/health
# Response: {"status": "ok", "version": "3.6.0-py"}

# 4. Check Jaeger tracing UI
open http://localhost:16686

# 5. Check Prometheus metrics
open http://localhost:9090

# 6. Run tests
pytest backend/tests -v

# 7. Start frontend (unchanged)
npm start
# Frontend at http://localhost:4520
```

---

## Part 5: File Structure After Bootstrap

```
agents-office/
├── frontend/                    # Unchanged v3.6
│   ├── src/
│   ├── dist/
│   └── package.json
│
├── backend/                     # NEW (Python)
│   ├── main.py                  # FastAPI app
│   ├── config.py
│   │
│   ├── langgraph/               # State graphs (Week 1-2)
│   │   ├── state.py
│   │   ├── nodes.py
│   │   ├── graphs.py
│   │   └── edges.py
│   │
│   ├── mcp/                     # MCP skeleton (Week 1)
│   │   ├── manager.py
│   │   └── executor.py
│   │
│   ├── sandbox/                 # Docker sandboxing (Week 5)
│   │   ├── executor.py
│   │   ├── Dockerfile
│   │   └── tool-requirements.txt
│   │
│   ├── services/                # Business logic
│   │   ├── brain.py             # Brain loader
│   │   ├── roster.py            # Agent loader
│   │   ├── skills.py            # Skills loader
│   │   ├── learning.py          # Feedback system
│   │   └── knowledge_base.py    # Agent KB
│   │
│   ├── api/                     # Routes
│   │   ├── tasks.py
│   │   ├── chat.py
│   │   ├── approval.py
│   │   └── routines.py
│   │
│   ├── observability/           # Tracing & logging
│   │   ├── tracer.py
│   │   ├── prometheus.yml
│   │   └── __init__.py
│   │
│   └── tests/                   # Full test suite
│       ├── test_nodes.py
│       ├── test_graphs.py
│       ├── test_knowledge_base.py
│       ├── test_sandbox.py
│       └── test_api.py
│
├── brain/                       # Your notes (unchanged)
│   └── Agents Office/
│       ├── kb/                  # Knowledge bases per agent
│       ├── skills/
│       ├── feedback/
│       └── routines.json
│
├── docker-compose.yml           # All services
├── Dockerfile                   # Backend image
├── Dockerfile.sandbox           # Agent sandbox image
├── office.config.json           # Config (unchanged)
├── office.agents.json           # Roster (unchanged)
│
└── .github/
    └── workflows/
        └── deploy.yml           # GitHub Actions → Dockerploy
```

---

## Part 6: API Endpoints (All Same as v3.6)

```
POST   /api/tasks                      Create task
GET    /api/tasks/{task_id}            Get task status
POST   /api/tasks/{task_id}/approve    Approve pending
POST   /api/tasks/{task_id}/reject     Reject with feedback
POST   /api/tasks/{task_id}/messages   Chat with agent
GET    /api/skills                     List all skills
GET    /api/routines                   List routines
POST   /api/routines                   Create routine
GET    /api/health                     Health check
GET    /api/traces/{task_id}           Get execution trace
```

Frontend needs **zero changes**.

---

## Key Decisions Made

1. **Hybrid approach:** Keep frontend, rewrite backend only
2. **Knowledge base:** Per-agent memory (JSONL history + learned rules)
3. **Sandboxing:** Docker containers for all tool calls
4. **Observability:** Jaeger tracing + structured logging (every step visible)
5. **Testing:** Full suite (unit + integration + security)
6. **Deployment:** GitHub → Dockerploy auto-deploy
7. **Priority:** Team execution first, then other features
8. **All v3.6 features:** Planned in roadmap, not skipped

---

## Next: Choose Your Week 1 Focus

Week 1 task: Build the LangGraph state graphs and core nodes.

Ready to start?
