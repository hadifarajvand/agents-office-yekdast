"""OpenHands CLI in headless mode (`openhands --headless --json -t ...`).

UNVERIFIED and the most uncertain adapter: the docs fetched while writing this did not
list the environment variables for the model (LLM_MODEL / LLM_API_KEY / LLM_BASE_URL are
the conventional names) nor the output event schema. The bake-off must confirm both
before this adapter is trusted; until then it reports no tokens and no models_seen.
"""
from __future__ import annotations

import json
from pathlib import Path

from ..config import load_config
from .base import ContainerWorker


class OpenHandsWorker(ContainerWorker):
    kind = "openhands"
    image_key = "openhands"

    def argv(self, limits):
        return ["openhands", "--headless", "--json", "-t",
                "Read /workspace/TASK.md and carry out the task completely. Run the tests until they pass."]

    def env(self, limits):
        cfg = load_config()
        model = limits.get("model") or cfg.roles["builder"]
        return {"LLM_MODEL": f"openai/{model}", "LLM_BASE_URL": f"{cfg.sandbox['router_gateway']}/v1",
                "LLM_API_KEY": "placeholder", "SANDBOX_VOLUMES": "/workspace:/workspace:rw"}

    def parse(self, stdout, out_dir: Path):
        events = 0
        for line in stdout.splitlines():
            try:
                json.loads(line)
                events += 1
            except ValueError:
                pass
        return {"tokens": 0, "usd": 0.0, "models_seen": [], "events": events}
