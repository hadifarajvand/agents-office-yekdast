# Multi-Agent Implementation Guide for Agent Office

**Status:** Ready for Phase 2 Development  
**Date:** 2026-09-18  
**Target:** Agent Office Backend (FastAPI + LangGraph + PostgreSQL)

---

## Quick Start: Phase 2 LangGraph Setup

### 1. Install Dependencies

```bash
pip install langgraph langchain-anthropic asyncpg
```

### 2. Core Files to Create

```
backend/
├── graph/
│   ├── __init__.py
│   ├── state.py           # OfficeState TypedDict
│   ├── nodes.py           # Node implementations
│   ├── graph.py           # StateGraph builder
│   └── checkpoint.py      # PostgreSQL checkpointing
├── services/
│   ├── orchestrator.py    # Main execution engine
│   └── permissions.py     # Tool sandbox
└── main.py                # Updated FastAPI
```

---

## Complete Implementation Templates

### 1. State Definition (`backend/graph/state.py`)

```python
"""
Core state structure for Agent Office
Flows through every node in the graph
"""

from typing import TypedDict, Literal, Sequence
from datetime import datetime

class OfficeState(TypedDict):
    """
    Shared state for all agents in the office
    This is the single source of truth as tasks flow through nodes
    """
    
    # ===== TASK DEFINITION =====
    task_id: str                    # Unique identifier (UUID)
    task_text: str                  # User's request
    department: str                 # Target department
    created_by: str                 # User email
    created_at: datetime            # Timestamp
    
    # ===== ROUTING & ASSIGNMENT =====
    status: Literal[
        "pending",                  # Awaiting processing
        "assigned",                 # Routed to department
        "working",                  # Agents executing
        "completed",                # Success
        "failed",                   # Error occurred
    ]
    
    assigned_lead: str              # Lead agent ID
    assigned_agents: list[str]      # Specialist agent IDs
    
    # ===== CONTEXT & KNOWLEDGE =====
    brain_context: list[dict]       # Relevant brain notes
    working_memory: dict            # Intermediate results
    
    # ===== MESSAGES & RESULTS =====
    messages: list[dict]            # Conversation history
    deliverable: str                # Final output
    
    # ===== TRACKING =====
    used_tools: list[str]           # MCP tools invoked
    costs: dict                     # Token usage per model
    errors: list[str]               # Error log

# Example initialization
def create_initial_state(
    task_id: str,
    task_text: str,
    created_by: str,
) -> OfficeState:
    """Create initial state for new task"""
    
    return {
        "task_id": task_id,
        "task_text": task_text,
        "department": "",
        "created_by": created_by,
        "created_at": datetime.now(),
        "status": "pending",
        "assigned_lead": "",
        "assigned_agents": [],
        "brain_context": [],
        "working_memory": {},
        "messages": [],
        "deliverable": "",
        "used_tools": [],
        "costs": {"haiku": 0, "sonnet": 0},
        "errors": [],
    }
```

### 2. Node Implementations (`backend/graph/nodes.py`)

```python
"""
Node implementations for OfficeGraph
Each node is an async function that processes state
"""

from typing import Callable
from langchain_anthropic import ChatAnthropic
from datetime import datetime
import asyncio

class NodeImplementations:
    """All graph nodes"""
    
    def __init__(self, config: dict, roster: dict, brain):
        self.config = config
        self.roster = roster
        self.brain = brain
        self.models = {
            "haiku": ChatAnthropic(model="claude-haiku-4-5-20251001"),
            "sonnet": ChatAnthropic(model="claude-sonnet-4"),
        }
    
    # ===== NODE: ROUTER =====
    
    async def router_node(self, state: OfficeState) -> OfficeState:
        """
        Route task to correct department
        Uses sonnet model for accuracy
        """
        
        router_prompt = f"""
        Classify this task into ONE of:
        - marketing: campaigns, research, content, analytics
        - support: customer issues, billing, escalations
        - engineering: code, infrastructure, deployment
        - research: analysis, data gathering, insights
        
        Task: {state['task_text']}
        
        Respond ONLY with the department name (lowercase).
        """
        
        response = await self.models["sonnet"].ainvoke(router_prompt)
        dept = response.content.strip().lower()
        
        # Validate
        valid = ["marketing", "support", "engineering", "research"]
        if dept not in valid:
            dept = "research"  # Safe fallback
        
        state["department"] = dept
        state["status"] = "assigned"
        state["messages"].append({
            "role": "router",
            "timestamp": datetime.now().isoformat(),
            "content": f"Routed to {dept} department",
        })
        
        return state
    
    # ===== NODE: BRAIN CONTEXT =====
    
    async def brain_context_node(self, state: OfficeState) -> OfficeState:
        """
        Retrieve relevant knowledge from brain
        Search by task text and department
        """
        
        # Search brain (assumes brain.search method exists)
        query = state["task_text"]
        dept_filter = state["department"]
        
        relevant_notes = self.brain.search(
            query=query,
            department=dept_filter,
            limit=5,
            min_score=0.3,
        )
        
        state["brain_context"] = relevant_notes
        state["messages"].append({
            "role": "system",
            "timestamp": datetime.now().isoformat(),
            "content": f"Retrieved {len(relevant_notes)} brain notes",
        })
        
        return state
    
    # ===== NODE: LEAD PLANNING =====
    
    async def lead_planning_node(self, state: OfficeState) -> OfficeState:
        """
        Lead agent plans approach
        Uses sonnet for strategic thinking
        """
        
        dept = state["department"]
        lead_agent = self.roster.get_lead_for_dept(dept)
        
        if not lead_agent:
            state["errors"].append(f"No lead found for {dept}")
            state["status"] = "failed"
            return state
        
        # Format context
        context_text = self._format_context(state["brain_context"])
        
        # Lead prompt
        lead_prompt = f"""
        You are the {dept.title()} Department Lead.
        
        Task: {state['task_text']}
        
        Available Context:
        {context_text}
        
        Create a clear execution plan:
        1. What's the objective?
        2. What specialists do you need? (research, writing, analysis, etc)
        3. What's the approach?
        4. Success criteria?
        
        Be concise but detailed. Your specialists will follow this plan.
        """
        
        response = await self.models["sonnet"].ainvoke(lead_prompt)
        plan = response.content
        
        state["assigned_lead"] = lead_agent["id"]
        state["assigned_agents"] = [
            s["id"] for s in self.roster.get_specialists_for_dept(dept)
        ]
        state["status"] = "working"
        state["messages"].append({
            "role": "lead",
            "timestamp": datetime.now().isoformat(),
            "content": plan,
        })
        state["working_memory"]["lead_plan"] = plan
        
        return state
    
    # ===== SPECIALIST NODES (Template) =====
    
    async def specialist_research_node(self, state: OfficeState) -> OfficeState:
        """Research specialist gathers information"""
        
        if state["status"] != "working":
            return state
        
        lead_plan = state["working_memory"].get("lead_plan", "")
        
        research_prompt = f"""
        You are a research specialist in {state['department']}.
        
        Task: {state['task_text']}
        
        Lead's Plan:
        {lead_plan}
        
        Your job: Find relevant data, trends, and evidence.
        Focus on: facts, sources, credibility, novelty.
        
        Provide actionable research.
        """
        
        response = await self.models["haiku"].ainvoke(research_prompt)
        
        state["working_memory"]["research"] = response.content
        state["messages"].append({
            "role": "research",
            "timestamp": datetime.now().isoformat(),
            "content": response.content[:300] + "...",
        })
        
        return state
    
    async def specialist_writing_node(self, state: OfficeState) -> OfficeState:
        """Writing specialist creates content"""
        
        if state["status"] != "working":
            return state
        
        lead_plan = state["working_memory"].get("lead_plan", "")
        research = state["working_memory"].get("research", "")
        
        writing_prompt = f"""
        You are a writing specialist in {state['department']}.
        
        Task: {state['task_text']}
        
        Lead's Plan:
        {lead_plan}
        
        Research Findings:
        {research}
        
        Your job: Create clear, compelling content based on research.
        Focus on: clarity, persuasion, brand voice consistency.
        """
        
        response = await self.models["haiku"].ainvoke(writing_prompt)
        
        state["working_memory"]["writing"] = response.content
        state["messages"].append({
            "role": "writing",
            "timestamp": datetime.now().isoformat(),
            "content": response.content[:300] + "...",
        })
        
        return state
    
    async def specialist_analysis_node(self, state: OfficeState) -> OfficeState:
        """Analysis specialist provides metrics and insights"""
        
        if state["status"] != "working":
            return state
        
        analysis_prompt = f"""
        You are an analysis specialist in {state['department']}.
        
        Task: {state['task_text']}
        
        Your job: Provide metrics, insights, ROI, risks, and opportunities.
        Focus on: numbers, trends, impact, data-driven recommendations.
        """
        
        response = await self.models["haiku"].ainvoke(analysis_prompt)
        
        state["working_memory"]["analysis"] = response.content
        state["messages"].append({
            "role": "analysis",
            "timestamp": datetime.now().isoformat(),
            "content": response.content[:300] + "...",
        })
        
        return state
    
    # ===== NODE: SYNTHESIS =====
    
    async def synthesis_node(self, state: OfficeState) -> OfficeState:
        """Lead synthesizes specialist outputs"""
        
        specialist_results = "\n".join([
            f"Research:\n{state['working_memory'].get('research', 'N/A')}",
            f"\nWriting:\n{state['working_memory'].get('writing', 'N/A')}",
            f"\nAnalysis:\n{state['working_memory'].get('analysis', 'N/A')}",
        ])
        
        synthesis_prompt = f"""
        As the {state['department']} lead, synthesize these results:
        
        Task: {state['task_text']}
        
        Specialist Outputs:
        {specialist_results[:1000]}
        
        Create a final, cohesive deliverable:
        1. Directly answers the task
        2. Incorporates all specialist insights
        3. Resolves any conflicts
        4. Immediately actionable
        
        Format as markdown.
        """
        
        response = await self.models["sonnet"].ainvoke(synthesis_prompt)
        
        state["deliverable"] = response.content
        state["messages"].append({
            "role": "lead",
            "timestamp": datetime.now().isoformat(),
            "content": "Synthesis complete",
        })
        
        return state
    
    # ===== NODE: BRAIN UPDATE =====
    
    async def brain_update_node(self, state: OfficeState) -> OfficeState:
        """Save results to brain as learning"""
        
        note = {
            "type": "task_result",
            "title": state["task_text"][:50],
            "department": state["department"],
            "task_id": state["task_id"],
            "content": state["deliverable"],
            "created_at": datetime.now().isoformat(),
            "created_by": state["created_by"],
            "tags": [state["department"]],
        }
        
        try:
            self.brain.save_note(note)
            state["messages"].append({
                "role": "system",
                "timestamp": datetime.now().isoformat(),
                "content": "Saved to brain",
            })
        except Exception as e:
            state["errors"].append(f"Brain save failed: {e}")
        
        return state
    
    # ===== NODE: COMPLETE =====
    
    async def complete_node(self, state: OfficeState) -> OfficeState:
        """Mark task complete"""
        state["status"] = "completed"
        return state
    
    # ===== UTILITIES =====
    
    def _format_context(self, notes: list) -> str:
        """Format brain notes for LLM prompt"""
        if not notes:
            return "No relevant context found"
        
        lines = []
        for note in notes[:3]:
            title = note.get("title", "Untitled")
            content = note.get("content", "")[:100]
            lines.append(f"- {title}: {content}...")
        
        return "\n".join(lines)
```

### 3. StateGraph Builder (`backend/graph/graph.py`)

```python
"""
Build the LangGraph StateGraph
Main orchestration engine
"""

from langgraph.graph import StateGraph, END
from .state import OfficeState
from .nodes import NodeImplementations

class OfficeGraph:
    """Main orchestration graph for Agent Office"""
    
    def __init__(self, config: dict, roster: dict, brain):
        self.config = config
        self.roster = roster
        self.brain = brain
        self.nodes = NodeImplementations(config, roster, brain)
        self.graph = self._build_graph()
    
    def _build_graph(self) -> StateGraph:
        """Build the complete state graph"""
        
        builder = StateGraph(OfficeState)
        
        # ===== ADD NODES =====
        builder.add_node("router", self.nodes.router_node)
        builder.add_node("brain_context", self.nodes.brain_context_node)
        builder.add_node("lead_planning", self.nodes.lead_planning_node)
        
        # Specialist nodes
        builder.add_node("specialist_research", self.nodes.specialist_research_node)
        builder.add_node("specialist_writing", self.nodes.specialist_writing_node)
        builder.add_node("specialist_analysis", self.nodes.specialist_analysis_node)
        
        # Synthesis & finalization
        builder.add_node("synthesis", self.nodes.synthesis_node)
        builder.add_node("brain_update", self.nodes.brain_update_node)
        builder.add_node("complete", self.nodes.complete_node)
        
        # ===== ADD EDGES =====
        
        # Start flow
        builder.add_edge("START", "router")
        builder.add_edge("router", "brain_context")
        builder.add_edge("brain_context", "lead_planning")
        
        # Parallel specialists
        builder.add_edge("lead_planning", "specialist_research")
        builder.add_edge("lead_planning", "specialist_writing")
        builder.add_edge("lead_planning", "specialist_analysis")
        
        # Join and synthesize
        builder.add_edge("specialist_research", "synthesis")
        builder.add_edge("specialist_writing", "synthesis")
        builder.add_edge("specialist_analysis", "synthesis")
        
        # Finalize
        builder.add_edge("synthesis", "brain_update")
        builder.add_edge("brain_update", "complete")
        builder.add_edge("complete", END)
        
        return builder.compile()
    
    async def execute(self, initial_state: OfficeState) -> OfficeState:
        """Execute the graph"""
        return await self.graph.ainvoke(initial_state)
```

### 4. PostgreSQL Checkpointing (`backend/graph/checkpoint.py`)

```python
"""
Save and restore state to PostgreSQL
Enables recovery from failures
"""

import asyncpg
import json
from datetime import datetime
from typing import Optional, Dict, Any

class PostgreSQLCheckpoint:
    """Checkpoint manager for LangGraph state"""
    
    def __init__(self, db_url: str):
        self.db_url = db_url
        self.pool = None
    
    async def initialize(self):
        """Create database pool and tables"""
        
        self.pool = await asyncpg.create_pool(
            self.db_url,
            min_size=2,
            max_size=10,
        )
        
        async with self.pool.acquire() as conn:
            # Create checkpoints table
            await conn.execute("""
                CREATE TABLE IF NOT EXISTS checkpoints (
                    checkpoint_id SERIAL PRIMARY KEY,
                    task_id VARCHAR(50) NOT NULL,
                    node_name VARCHAR(100) NOT NULL,
                    state_data JSONB NOT NULL,
                    timestamp TIMESTAMP DEFAULT NOW(),
                    status VARCHAR(20) NOT NULL,
                    error_message TEXT,
                    
                    UNIQUE(task_id, node_name),
                    INDEX task_idx (task_id),
                    INDEX status_idx (status)
                )
            """)
            
            print("[INIT] Checkpoints table ready")
    
    async def save(
        self,
        task_id: str,
        node_name: str,
        state: Dict[str, Any],
        status: str = "success",
        error: Optional[str] = None,
    ) -> int:
        """Save checkpoint"""
        
        async with self.pool.acquire() as conn:
            checkpoint_id = await conn.fetchval("""
                INSERT INTO checkpoints 
                (task_id, node_name, state_data, status, error_message)
                VALUES ($1, $2, $3, $4, $5)
                ON CONFLICT (task_id, node_name) DO UPDATE 
                SET state_data = $3, status = $4, error_message = $5
                RETURNING checkpoint_id
            """, task_id, node_name, json.dumps(state, default=str), status, error)
            
            return checkpoint_id
    
    async def load(
        self,
        task_id: str,
        node_name: str,
    ) -> Optional[Dict[str, Any]]:
        """Load checkpoint"""
        
        async with self.pool.acquire() as conn:
            row = await conn.fetchrow("""
                SELECT state_data, status
                FROM checkpoints
                WHERE task_id = $1 AND node_name = $2
            """, task_id, node_name)
            
            if not row:
                return None
            
            return {
                "state": json.loads(row["state_data"]),
                "status": row["status"],
            }
    
    async def get_latest_node(self, task_id: str) -> Optional[str]:
        """Get last executed node"""
        
        async with self.pool.acquire() as conn:
            return await conn.fetchval("""
                SELECT node_name
                FROM checkpoints
                WHERE task_id = $1 AND status = 'success'
                ORDER BY timestamp DESC
                LIMIT 1
            """, task_id)

# Usage in FastAPI
checkpoint_store = None

async def get_checkpoint_store() -> PostgreSQLCheckpoint:
    global checkpoint_store
    if checkpoint_store is None:
        checkpoint_store = PostgreSQLCheckpoint(
            os.getenv("DATABASE_URL", "postgresql://localhost/agent_office")
        )
        await checkpoint_store.initialize()
    return checkpoint_store
```

### 5. FastAPI Integration (`backend/main.py` - updated)

```python
"""
Updated FastAPI endpoints for LangGraph execution
"""

from fastapi import FastAPI, HTTPException
from datetime import datetime
import uuid
import asyncio

app = FastAPI()

# Global graph instance
office_graph = None
checkpoint_store = None

@app.on_event("startup")
async def startup():
    """Initialize graph and checkpoint store"""
    global office_graph, checkpoint_store
    
    config = get_config()
    roster = load_roster()
    brain = load_brain()
    
    # Initialize graph
    office_graph = OfficeGraph(config, roster, brain)
    
    # Initialize checkpoint store
    checkpoint_store = PostgreSQLCheckpoint(
        os.getenv(
            "DATABASE_URL",
            "postgresql://localhost/agent_office",
        )
    )
    await checkpoint_store.initialize()
    
    print("[START] OfficeGraph and checkpoints ready")

@app.post("/api/tasks")
async def create_task(body: dict):
    """Create and execute task"""
    
    if "department" not in body or "text" not in body:
        raise HTTPException(status_code=400, detail="Missing fields")
    
    # Create task
    task_id = str(uuid.uuid4())[:8]
    initial_state = create_initial_state(
        task_id=task_id,
        task_text=body["text"],
        created_by=body.get("created_by", "unknown"),
    )
    
    # Save initial checkpoint
    await checkpoint_store.save(
        task_id=task_id,
        node_name="START",
        state=initial_state,
        status="pending",
    )
    
    # Execute in background
    asyncio.create_task(execute_task_background(task_id, initial_state))
    
    return {
        "task_id": task_id,
        "status": "pending",
        "created_at": datetime.now().isoformat(),
    }

async def execute_task_background(task_id: str, initial_state: OfficeState):
    """Execute task and save checkpoints"""
    
    try:
        # Execute graph
        final_state = await office_graph.execute(initial_state)
        
        # Save final checkpoint
        await checkpoint_store.save(
            task_id=task_id,
            node_name="COMPLETE",
            state=final_state,
            status="success",
        )
        
        print(f"[✓] Task {task_id} complete")
    
    except Exception as e:
        print(f"[✗] Task {task_id} failed: {e}")
        
        # Save error checkpoint
        await checkpoint_store.save(
            task_id=task_id,
            node_name="ERROR",
            state={"error": str(e)},
            status="failed",
            error=str(e),
        )

@app.get("/api/tasks/{task_id}")
async def get_task(task_id: str):
    """Get task status"""
    
    # Load latest checkpoint
    latest_node = await checkpoint_store.get_latest_node(task_id)
    
    if not latest_node:
        raise HTTPException(status_code=404, detail="Task not found")
    
    checkpoint = await checkpoint_store.load(task_id, latest_node)
    state = checkpoint["state"]
    
    return {
        "task_id": task_id,
        "status": state["status"],
        "deliverable": state.get("deliverable", ""),
        "messages_count": len(state["messages"]),
        "used_tools": state["used_tools"],
        "errors": state["errors"],
    }
```

---

## System Prompts for Agent Office

### Marketing Department

```python
SYSTEM_PROMPTS = {
    "marketing_lead": """
You are the Marketing Department Lead in Agent Office.

## Your Role
Strategic orchestrator of marketing initiatives. You plan campaigns, coordinate specialists, and make go/no-go decisions.

## Your Responsibilities
- Understand task objectives clearly
- Create detailed execution plans
- Assign specialists appropriately
- Synthesize results into cohesive campaigns
- Ensure brand voice consistency

## Constraints
- DO NOT conduct research yourself (specialists handle that)
- DO NOT approve budgets (that's finance)
- DO communicate clearly with your team

## Your Success Criteria
- Campaign briefs are actionable within 2 hours
- All specialist inputs are incorporated
- Deliverables are zero-error ready

Be strategic, decisive, and concise.
""",

    "marketing_research": """
You are a Research Specialist in the Marketing Department.

## Your Role
Find market intelligence, trends, competitor moves, and customer insights.

## Your Responsibilities
- Search for relevant data and trends
- Analyze competitor landscape
- Identify market opportunities
- Provide credible, sourced findings

## Constraints
- DO NOT write marketing copy (writing team does that)
- DO NOT make strategic decisions (lead does that)
- DO provide citations for all findings

## Your Success Criteria
- Sources are credible and cited
- Findings are novel and actionable
- Data is current (within 30 days)

Be thorough, accurate, and specific.
""",

    "marketing_writing": """
You are a Copy Specialist in the Marketing Department.

## Your Role
Create persuasive, on-brand marketing content.

## Your Responsibilities
- Write campaign briefs and marketing copy
- Ensure brand voice consistency
- Translate research into compelling messaging
- Focus on customer benefits

## Constraints
- DO follow brand guidelines strictly
- DO base copy on research (not guessing)
- DO NOT conduct your own research
- DO NOT approve campaigns

## Your Success Criteria
- Copy is persuasive and clear
- Brand voice is consistent
- Every claim is backed by research

Be creative, concise, and data-driven.
""",

    "marketing_analysis": """
You are an Analytics Specialist in the Marketing Department.

## Your Role
Provide metrics, ROI projections, and data-driven insights.

## Your Responsibilities
- Analyze campaign performance potential
- Provide ROI estimates
- Identify risks and opportunities
- Support decision-making with data

## Constraints
- DO base analysis on hard data
- DO provide confidence intervals
- DO NOT make strategic decisions

## Your Success Criteria
- Analysis is quantitative
- Assumptions are clearly stated
- Recommendations are data-backed

Be precise, analytical, and honest about uncertainty.
""",
}
```

### Engineering Department

```python
    "engineering_lead": """
You are the Engineering Lead in Agent Office.

## Your Role
Technical architect and team orchestrator. You design solutions and coordinate developers.

## Your Responsibilities
- Understand technical requirements
- Design architecture and APIs
- Coordinate backend, frontend, DevOps
- Code review and quality assurance

## Constraints
- DO NOT write all code yourself (specialists do that)
- DO NOT deploy to production (DevOps does that)
- DO ensure architectural consistency

## Your Success Criteria
- Architecture is scalable and maintainable
- Code reviews catch issues before deployment
- All tests pass before release

Be pragmatic, thorough, and collaborative.
""",

    "engineering_backend": """
You are a Backend Specialist in the Engineering Department.

## Your Role
Develop APIs, services, and backend systems.

## Your Responsibilities
- Write clean, tested Python/Node backend code
- Design data models
- Implement business logic
- Document APIs

## Constraints
- DO write tests for all code (100% coverage)
- DO document your work
- DO NOT deploy to production
- DO NOT skip code review

## Your Success Criteria
- All tests pass
- Code is reviewed and approved
- APIs are documented

Be quality-focused, pragmatic, and collaborative.
""",
}
```

---

## Permission Setup

```python
# backend/services/permissions.py

from typing import Set, Tuple

class PermissionMatrix:
    """Tool access control for departments"""
    
    DEPT_PERMISSIONS = {
        "marketing": {
            ("web_search", "execute"),
            ("file_read", "read"),
            ("file_write", "write"),
            ("google_drive", "read"),
        },
        "support": {
            ("knowledge_base_search", "read"),
            ("customer_data_read", "read"),
            ("ticket_write", "write"),
            ("email_send", "execute"),
        },
        "engineering": {
            ("github_read", "read"),
            ("github_write", "write"),
            ("database_read", "read"),
            ("docker_build", "execute"),
            # NOTE: No kubernetes_write - Phase 5
        },
        "research": {
            ("web_search", "execute"),
            ("file_read", "read"),
            ("file_write", "write"),
        },
    }
    
    @staticmethod
    def can_access(dept: str, tool: str, action: str) -> bool:
        """Check permission"""
        perms = PermissionMatrix.DEPT_PERMISSIONS.get(dept, set())
        return (tool, action) in perms
```

---

## Deployment Checklist for Phase 2

### Pre-Deployment
- [ ] PostgreSQL database initialized
- [ ] All nodes tested individually
- [ ] State schema validates
- [ ] Checkpointing working
- [ ] Permissions matrix configured

### Runtime Checks
- [ ] Graph compiles without errors
- [ ] At least one full workflow runs end-to-end
- [ ] Checkpoints save/load correctly
- [ ] Brain integration works
- [ ] Error handling catches exceptions

### Post-Deployment
- [ ] Monitor task completion rates
- [ ] Check checkpoint storage (shouldn't grow unbounded)
- [ ] Verify deliverables are being saved to brain
- [ ] Monitor token usage per model
- [ ] Track common errors/escalations

---

## Example: Execute a Task End-to-End

```python
import asyncio
from datetime import datetime

async def test_workflow():
    """Test complete workflow"""
    
    # Setup (done in startup)
    config = get_config()
    roster = load_roster()
    brain = load_brain()
    
    graph = OfficeGraph(config, roster, brain)
    checkpoint_store = PostgreSQLCheckpoint(db_url)
    await checkpoint_store.initialize()
    
    # Create task
    task_id = "test_001"
    state = create_initial_state(
        task_id=task_id,
        task_text="Create Q3 marketing campaign brief",
        created_by="test@example.com",
    )
    
    # Save initial checkpoint
    await checkpoint_store.save(
        task_id=task_id,
        node_name="START",
        state=state,
    )
    
    # Execute
    print(f"\n[{task_id}] Starting execution...")
    
    try:
        final_state = await graph.execute(state)
        
        # Save final checkpoint
        await checkpoint_store.save(
            task_id=task_id,
            node_name="COMPLETE",
            state=final_state,
            status="success",
        )
        
        print(f"\n[{task_id}] ✓ Complete")
        print(f"Deliverable:\n{final_state['deliverable']}")
        print(f"\nMessages: {len(final_state['messages'])}")
        print(f"Errors: {len(final_state['errors'])}")
        
    except Exception as e:
        print(f"\n[{task_id}] ✗ Failed: {e}")
        
        await checkpoint_store.save(
            task_id=task_id,
            node_name="ERROR",
            state={"error": str(e)},
            status="failed",
            error=str(e),
        )

# Run test
# asyncio.run(test_workflow())
```

---

## Next Steps

1. **Week 1**: Implement state, nodes, graph
2. **Week 2**: Add checkpointing and FastAPI endpoints
3. **Week 3**: Integrate brain and permissions
4. **Week 4**: Testing and documentation

---

## References

- LangGraph Docs: https://langchain-ai.github.io/langgraph/
- Anthropic Claude Models: https://docs.anthropic.com/
- Agent Office Architecture: See PHASE_2_DESIGN.md
