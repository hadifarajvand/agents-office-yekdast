"""Build workers: the coding agent that turns a scoped job into a patch. One interface
(pipeline.ports.BuildWorker), several adapters; config.worker.kind picks one."""
from __future__ import annotations

from ..config import load_config


def make_worker(kind: str | None = None):
    kind = kind or load_config().worker.get("kind", "fake")
    if kind == "claude_code":
        from .claude_code import ClaudeCodeWorker
        return ClaudeCodeWorker()
    if kind == "mini_swe":
        from .mini_swe import MiniSweWorker
        return MiniSweWorker()
    if kind == "openhands":
        from .openhands import OpenHandsWorker
        return OpenHandsWorker()
    if kind == "fake":
        import logging
        logging.getLogger("agents_office.worker").warning("worker.kind is fake: builds will fail their checks; set it to claude_code")
        from .fake import FakeWorker
        return FakeWorker()
    raise ValueError(f'unknown worker kind "{kind}" (claude_code, mini_swe, openhands, fake)')
