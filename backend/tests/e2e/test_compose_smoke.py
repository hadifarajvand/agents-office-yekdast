"""Task 8: codifies the already-manually-verified `docker compose up --build` flow.
Boots the real stack (app + postgres + redis), waits for health, hits /api/health,
creates a task, approves it through the routine run/approve path, polls /api/tasks
until complete, and checks the exact JSON shape src/tasks.js expects.

This spins up and tears down real containers, so it's opt-in: skipped unless
RUN_E2E_COMPOSE=1 is set. It uses its own compose project name ("ao-e2e") and its
own host port (4521, not the dev stack's 4520) so it never touches a stack a
developer already has running — teardown only ever stops what this test started.
"""
from __future__ import annotations

import os
import subprocess
import time
import uuid
from pathlib import Path

import httpx
import pytest

ROOT = Path(__file__).resolve().parents[3]
PROJECT = "ao-e2e"
PORT = 4521
BASE_URL = f"http://localhost:{PORT}"
OVERRIDE_FILE = ROOT / "docker-compose.e2e-override.yml"

pytestmark = pytest.mark.skipif(
    os.environ.get("RUN_E2E_COMPOSE") != "1",
    reason="boots real docker-compose containers; set RUN_E2E_COMPOSE=1 to run",
)


def _compose(*args: str) -> subprocess.CompletedProcess:
    return subprocess.run(
        ["docker", "compose", "-p", PROJECT, "-f", "docker-compose.yml", "-f", str(OVERRIDE_FILE), *args],
        cwd=ROOT, capture_output=True, text=True, timeout=300,
    )


@pytest.fixture(scope="module")
def compose_stack(tmp_path_factory):
    """Boots an isolated stack under its own project name/port/brain dir, and
    tears down only that project's containers and volumes — never the dev stack."""
    brain_dir = tmp_path_factory.mktemp("e2e-brain")
    OVERRIDE_FILE.write_text(
        "services:\n"
        "  app:\n"
        f"    ports:\n"
        f"      - \"{PORT}:4520\"\n"
        f"    volumes:\n"
        f"      - {brain_dir}:/brain\n"
    )
    try:
        up = _compose("up", "-d", "--build")
        assert up.returncode == 0, f"docker compose up failed:\n{up.stdout}\n{up.stderr}"

        deadline = time.time() + 120
        last_error = None
        while time.time() < deadline:
            try:
                r = httpx.get(f"{BASE_URL}/api/health", timeout=5)
                if r.status_code == 200 and r.json().get("ok"):
                    break
            except httpx.HTTPError as e:
                last_error = e
            time.sleep(2)
        else:
            raise TimeoutError(f"stack never became healthy: {last_error}")

        yield BASE_URL
    finally:
        _compose("down", "-v")
        OVERRIDE_FILE.unlink(missing_ok=True)


def test_health_reports_ok_with_expected_shape(compose_stack):
    r = httpx.get(f"{compose_stack}/api/health", timeout=10)
    assert r.status_code == 200
    body = r.json()
    for key in ("ok", "version", "backend", "model", "depts", "agents", "roster", "skills", "mcp"):
        assert key in body, f"/api/health missing {key!r}"
    assert body["ok"] is True
    assert body["backend"] == "langgraph"
    assert isinstance(body["agents"], int) and body["agents"] == 35
    assert len(body["depts"]) == 8


def test_create_run_task_reaches_done_with_frontend_shape(compose_stack):
    """The direct create -> run path (src/tasks.js's blocking call) always
    completes synchronously, independent of needsOk (Task 4's gate only
    engages for the routine draft/approve path, exercised below)."""
    create = httpx.post(
        f"{compose_stack}/api/tasks",
        json={"dept": "content", "text": f"e2e smoke {uuid.uuid4()}: say hello in one sentence"},
        timeout=30,
    )
    assert create.status_code == 200
    task = create.json()
    for key in ("id", "dept", "text", "state", "agent", "title", "plan", "eta_minutes", "why", "needsOk", "createdAt"):
        assert key in task, f"created task missing {key!r}"
    assert task["state"] == "next"

    run = httpx.post(f"{compose_stack}/api/tasks/{task['id']}/run", timeout=120)
    assert run.status_code == 200
    done = run.json()
    assert done["state"] == "done"
    assert not done.get("error")
    for key in ("result", "skills", "modelUsed", "modelFrom", "effortUsed", "effortFrom"):
        assert key in done, f"completed task missing {key!r}"
    assert isinstance(done["result"], str) and done["result"]

    listed = httpx.get(f"{compose_stack}/api/tasks", timeout=10).json()
    assert any(t["id"] == task["id"] and t["state"] == "done" for t in listed)


def test_routine_run_approve_flow_reaches_done(compose_stack):
    """The needsOk gate (Task 4): a routine fires into "waiting" with a draft,
    then /approve resumes the same paused graph and the task reaches "done"."""
    routine_id = f"e2e-{uuid.uuid4().hex[:8]}"
    created = httpx.post(
        f"{compose_stack}/api/routines",
        json={
            "id": routine_id, "dept": "fin", "agent": "invo",
            "title": "E2E smoke routine", "text": "Say hello in one sentence.",
            "when": {"kind": "daily", "at": "09:00"}, "needsOk": True,
        },
        timeout=10,
    )
    assert created.status_code == 200, created.text

    fired = httpx.post(f"{compose_stack}/api/routines/{routine_id}/run", timeout=30)
    assert fired.status_code == 200
    assert fired.json().get("ok") is True

    deadline = time.time() + 60
    task = None
    while time.time() < deadline:
        tasks = httpx.get(f"{compose_stack}/api/tasks", timeout=10).json()
        candidates = [t for t in tasks if t.get("agent") == "invo" and t.get("state") in ("waiting", "doing")]
        if candidates and candidates[0]["state"] == "waiting":
            task = candidates[0]
            break
        time.sleep(2)
    assert task is not None, "routine task never reached waiting"
    assert "draft" in task and task["draft"]
    assert "ask" in task

    approve = httpx.post(f"{compose_stack}/api/tasks/{task['id']}/approve", timeout=10)
    assert approve.status_code == 200
    assert approve.json() == {"ok": True, "id": task["id"], "state": "doing"}

    deadline = time.time() + 60
    final = None
    while time.time() < deadline:
        tasks = httpx.get(f"{compose_stack}/api/tasks", timeout=10).json()
        match = next((t for t in tasks if t["id"] == task["id"]), None)
        if match and match["state"] == "done":
            final = match
            break
        time.sleep(2)
    assert final is not None, "approved task never reached done"
    assert not final.get("error")
    assert final["result"]

    httpx.delete(f"{compose_stack}/api/routines/{routine_id}", timeout=10)
