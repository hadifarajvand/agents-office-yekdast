"""A worker that does nothing but report success. The default until the bake-off picks
a real one, so the pipeline can be started and clicked through without a container."""
from __future__ import annotations

from pathlib import Path

from ..config import load_config


class FakeWorker:
    async def run(self, job_dir: Path, brief: dict, limits: dict) -> dict:
        out = Path(job_dir) / "out"
        out.mkdir(parents=True, exist_ok=True)
        (out / "patch.bundle").write_text("fake bundle\n")
        (out / "agent.stdout").write_text("fake worker: no code was written\n")
        return {"patch_path": str(out / "patch.bundle"), "log_path": str(out / "agent.stdout"), "tokens": 0,
                "usd": 0.0, "models_seen": [load_config().roles.get("builder", "")], "exit_state": "ok"}
