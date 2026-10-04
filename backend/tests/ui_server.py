"""A real office server for browser tests: real FastAPI app, real Postgres, real LangGraph
checkpointer; only the outside world is scripted (models, build worker, Dokploy, checks).

    DATABASE_URL=postgresql://office:office@localhost:5432/office_ui \
    AO_BRAIN=/tmp/ui-brain python -m tests.ui_server 4597

Used by `npm run check` (check.mjs) to drive the page with headless Chromium."""
from __future__ import annotations

import os
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import uvicorn  # noqa: E402

from app import deps as deps_mod  # noqa: E402
from app.graph import engine  # noqa: E402
from app.pipeline.ports import Deps  # noqa: E402
from test_pipeline import FakeChecks, FakeDeployer, FakeWorker, Script  # noqa: E402

from app.config import load_config  # noqa: E402
from app.pipeline import exposure as _exp  # noqa: E402

load_config().pipeline["live_departments"] = list(_exp.ALL_DEPTS)  # the UI smoke walks a gated job through every lead

script, worker, deployer, checks = Script(), FakeWorker(), FakeDeployer(), FakeChecks()


async def route_json(system, user):
    return {"agent": None, "title": "UI smoke task", "plan": ["one step"], "eta_minutes": 1, "why": "scripted", "needs_ok": False}


async def ask(system, user, **kw):
    return "scripted reply"


async def ask_with_tools(messages, tools, **kw):
    return {"content": "scripted task result", "tool_calls": []}


engine.ask_haiku_json, engine.ask, engine.ask_with_tools = route_json, ask, ask_with_tools
deps_mod.build_deps = lambda: Deps(chat_json=script.chat_json, worker=worker, deployer=deployer, checks=checks,
                                   jobs_dir=Path(os.environ.get("AO_BRAIN", "/tmp")) / "jobs")

if __name__ == "__main__":
    from app.main import app
    uvicorn.run(app, host="127.0.0.1", port=int(sys.argv[1]) if len(sys.argv) > 1 else 4597, log_level="warning")
