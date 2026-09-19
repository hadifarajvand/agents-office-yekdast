"""Agents Office Backend v3.6.0-py (FastAPI)

Main server entry point. Loads config, roster, brain.
Serves API matching v3.6 frontend expectations.
"""

from datetime import datetime
from typing import List

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import StreamingResponse
import uvicorn
import json

from backend.config import get_config
from backend.services.roster import load_roster, get_agents_by_dept
from backend.services.brain import load_brain
from backend.services.task_executor import get_task_executor
from backend.schemas import (
    TaskResponse,
    TaskFrontendState,
    HealthResponse,
)
from backend.events import event_bus

# Initialize
app = FastAPI(
    title="Agents Office Backend",
    version="3.6.0-py",
    description="Python rewrite of Agents Office v3.6 backend with LangGraph orchestration",
)

# CORS: allow frontend at different ports
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:4520", "http://localhost:3000"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Load config once at startup
config = get_config()

print(f"[INFO] Agents Office {config['name']}")
print(f"[INFO] Backend: FastAPI on port {config['port']}")
print(f"[INFO] Brain: {config['brain_path']}")
print(f"[INFO] Model: {config['model']}")

# Show Claude backend
if config.get("anthropic_base_url"):
    print(f"[INFO] Claude: Local at {config['anthropic_base_url']}")
elif config.get("anthropic_api_key"):
    print("[INFO] Claude: Cloud API")
else:
    print(
        "[WARN] Claude: No auth configured (ANTHROPIC_AUTH_TOKEN or ANTHROPIC_API_KEY)"
    )

# Load roster
roster = load_roster()
print(
    f"[INFO] Agents: {len(roster['agents'])} ({roster['customized']} customized, {roster['briefed']} with briefs)"
)
for problem in roster["problems"][:3]:
    print(f"[WARN] {problem}")

# Load brain
brain = load_brain()
print(f"[INFO] Brain: {len(brain['all_notes'])} notes")

# Initialize services
task_executor = get_task_executor()

# In-memory store (replace with DB in Phase 8)
TASKS = {}
ROUTINES = {}

# ============ Health Check ============


@app.get("/api/health", response_model=HealthResponse)
async def health():
    """GET /api/health: Service health"""
    return HealthResponse(
        ok=True,
        status="ok",
        version="3.6.0-py",
        backend="fastapi",
        model=config["model"],
        brain=str(config["brain_path"]),
        agents=len(roster["agents"]),
        notes=len(brain["all_notes"]),
        timestamp=datetime.now().isoformat(),
    )


# ============ Real-Time Events (SSE) ============


@app.get("/api/events")
async def events_stream():
    """Server-Sent Events stream for real-time updates

    Clients connect here and receive task events as they happen:
    - task:created
    - task:started
    - task:progress
    - task:completed
    - task:failed
    - ping (keepalive)
    """

    async def event_generator():
        try:
            async for event in event_bus.subscribe(timeout=30):
                yield f"data: {json.dumps(event)}\n\n"
        except Exception as e:
            print(f"[SSE] Error in event stream: {e}")

    return StreamingResponse(event_generator(), media_type="text/event-stream")


@app.get("/api/metrics")
async def metrics():
    """Monitoring endpoint for health and diagnostics"""
    return {
        "ok": True,
        "sse": event_bus.get_stats(),
        "tasks": {
            "total": len(task_executor.active_tasks),
            "by_status": _count_tasks_by_status(),
        },
        "timestamp": datetime.now().isoformat(),
    }


def _count_tasks_by_status():
    """Count tasks by status"""
    counts = {"pending": 0, "doing": 0, "done": 0, "waiting": 0}
    for t in task_executor.active_tasks.values():
        status = t.get("status", "pending")
        if status in counts:
            counts[status] += 1
    return counts


# ============ Tasks API ============


@app.get("/api/tasks", response_model=List[TaskResponse])
async def list_tasks():
    """GET /api/tasks: List all tasks with normalized schema"""
    result = []

    for task_id, t in task_executor.active_tasks.items():
        # Ensure assigned_lead always has a value (never null)
        lead = t.get("assigned_lead")
        if not lead:
            # Fallback: get department lead from roster
            dept = t.get("department", "")
            dept_agents = get_agents_by_dept(dept)
            dept_lead = next((a["id"] for a in dept_agents if a.get("lead")), None)
            lead = dept_lead or f"lead_{dept}" or "unknown"

        result.append(
            TaskResponse(
                id=t.get("task_id", ""),
                agent=lead,
                dept=t.get("department", ""),
                title=t.get("task_text", "Task"),
                state=_normalize_state(t.get("status", "pending")),
                by=t.get("created_by", "backend"),
                createdAt=int(t.get("created_at", 0) * 1000),
                updatedAt=int(t.get("created_at", 0) * 1000),
                model=t.get("model", "sonnet"),
                effort=t.get("effort", "low"),
                live=True,
            )
        )

    return result


def _normalize_state(backend_state: str) -> TaskFrontendState:
    """Map backend status to frontend state"""
    status_map = {
        "pending": TaskFrontendState.NEXT,
        "pending_approval": TaskFrontendState.WAITING,
        "doing": TaskFrontendState.DOING,
        "done": TaskFrontendState.DONE,
    }
    return status_map.get(backend_state, TaskFrontendState.NEXT)


@app.post("/api/tasks")
async def create_task(body: dict):
    """POST /api/tasks: Create task

    Body: {department, text, model?, effort?, is_team_task?}
    Response: {task_id, status, created_at}
    """

    if "department" not in body or "text" not in body:
        raise HTTPException(status_code=400, detail="Missing department or text")

    # Validate department
    agents_in_dept = get_agents_by_dept(body["department"])
    if not agents_in_dept:
        raise HTTPException(
            status_code=400, detail=f"Department '{body['department']}' not found"
        )

    # Execute task through LangGraph
    task_id = await task_executor.execute_task(
        department=body["department"],
        task_text=body["text"],
        model=body.get("model", config["model"]),
        effort=body.get("effort", "low"),
        created_by=body.get("created_by", "api"),
    )

    task_state = await task_executor.get_task_status(task_id)

    return {
        "task_id": task_id,
        "status": task_state.get("status", "pending") if task_state else "pending",
        "department": body["department"],
        "created_at": int(datetime.now().timestamp() * 1000),
    }


@app.get("/api/tasks/{task_id}")
async def get_task(task_id: str):
    """GET /api/tasks/{task_id}: Get task status"""

    task_state = await task_executor.get_task_status(task_id)
    if not task_state:
        raise HTTPException(status_code=404, detail="Task not found")

    return {
        "task_id": task_id,
        "status": task_state.get("status"),
        "deliverable": task_state.get("deliverable"),
        "used_tools": task_state.get("used_tools", []),
        "errors": task_state.get("errors", []),
        "assigned_lead": task_state.get("assigned_lead"),
        "specialist_results": task_state.get("specialist_results", {}),
        "total_tokens": task_state.get("total_tokens", 0),
        "cost_usd": task_state.get("cost_usd", 0.0),
    }


@app.post("/api/tasks/{task_id}/approve")
async def approve_task(task_id: str, body: dict = None):
    """POST /api/tasks/{task_id}/approve: Approve pending task"""

    feedback = (body or {}).get("feedback", "") if body else ""
    approved = await task_executor.approve_task(task_id, feedback)

    if not approved:
        raise HTTPException(status_code=404, detail="Task not found")

    return {"approved": True}


@app.post("/api/tasks/{task_id}/reject")
async def reject_task(task_id: str, body: dict = None):
    """POST /api/tasks/{task_id}/reject: Reject with feedback"""

    reason = (body or {}).get("reason", "") if body else ""
    rejected = await task_executor.reject_task(task_id, reason)

    if not rejected:
        raise HTTPException(status_code=404, detail="Task not found")

    return {"rejected": True}


@app.post("/api/tasks/{task_id}/messages")
async def send_chat_message(task_id: str, body: dict):
    """POST /api/tasks/{task_id}/messages: Chat with agent

    Body: {message}
    Response: {response, agent_id}
    """

    if task_id not in TASKS:
        raise HTTPException(status_code=404, detail="Task not found")

    if "message" not in body:
        raise HTTPException(status_code=400, detail="Missing message")

    # Placeholder: just echo back
    # Week 1: integrate with LangGraph nodes
    return {
        "message": body["message"],
        "response": f"Echo: {body['message'][:50]}...",
        "agent_id": "placeholder",
    }


# ============ Routines API (Placeholder) ============


@app.get("/api/routines")
async def list_routines():
    """GET /api/routines: List all routines"""
    return []


@app.post("/api/routines")
async def create_routine(body: dict):
    """POST /api/routines: Create routine"""
    return {"routine_id": "placeholder"}


# ============ Agents API ============


@app.get("/api/agents")
async def list_agents():
    """GET /api/agents: List all agents"""
    return {
        "agents": roster["agents"],
        "count": len(roster["agents"]),
        "customized": roster["customized"],
        "briefed": roster["briefed"],
    }


# ============ Brain API ============


@app.get("/api/brain/notes")
async def list_brain_notes():
    """GET /api/brain/notes: List all brain notes"""
    return {
        "notes": brain["all_notes"][:100],  # paginate
        "total": len(brain["all_notes"]),
    }


# ============ Skills API (Placeholder) ============


@app.get("/api/skills")
async def list_skills():
    """GET /api/skills: List skills"""
    # Week 2+: load from <brain>/Agents Office/skills/
    return []


# ============ Startup/Shutdown ============


@app.on_event("startup")
async def startup():
    """Initialize services on startup"""
    print("[START] Server initialized")


@app.on_event("shutdown")
async def shutdown():
    """Cleanup on shutdown"""
    print("[STOP] Server shutting down")


# ============ Main ============

if __name__ == "__main__":
    port = config.get("port", 8000)
    print(f"\n[START] Starting on http://localhost:{port}")
    print(f"[DOCS] Docs at http://localhost:{port}/docs")
    print(f"[BRAIN] Brain at {config['brain_path']}\n")

    uvicorn.run(
        "backend.main:app", host="0.0.0.0", port=port, reload=False, log_level="info"
    )
