"""mini-swe-agent (`mini -t ... -y`), run with its local environment because the whole
container is already the sandbox. Model access through LiteLLM with an OpenAI-compatible
api_base pointing at the router gateway.

UNVERIFIED until the bake-off: the trajectory JSON field names (info.model_stats), and
how LiteLLM prefixes the model name for the router. Cost reported by mini is LiteLLM's
estimate and is 0 for models it does not know; the platform's own cost log is the
source of truth.
"""
from __future__ import annotations

import json
from pathlib import Path

from ..config import load_config
from .base import ContainerWorker


class MiniSweWorker(ContainerWorker):
    kind = "mini_swe"
    image_key = "mini_swe"

    def argv(self, limits):
        cfg = load_config()
        model = limits.get("model") or cfg.roles["builder"]
        return ["mini", "-t", "Read /workspace/TASK.md and carry out the task completely. Run the tests until they pass.",
                "-y", "-m", f"openai/{model}", "--environment-class", "local",
                "-c", "mini.yaml", "-c", f"model.model_kwargs.api_base={cfg.sandbox['router_gateway']}/v1",
                "-l", str(limits.get("cost_limit", 5.0)), "-o", "/out/trajectory.json"]

    def env(self, limits):
        return {"OPENAI_API_KEY": "placeholder", "MSWEA_CONFIGURED": "true"}

    def parse(self, stdout, out_dir: Path):
        traj = Path(out_dir) / "trajectory.json"
        if not traj.exists():
            return {}
        d = json.loads(traj.read_text())
        stats = ((d.get("info") or {}).get("model_stats") or {})
        model = load_config().roles["builder"]
        return {"tokens": int(stats.get("tokens", 0) or 0), "usd": float(stats.get("instance_cost", 0.0) or 0.0),
                "models_seen": [model] if stats.get("api_calls") else []}
