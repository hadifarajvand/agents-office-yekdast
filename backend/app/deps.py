"""Builds the pipeline's dependencies from configuration. Called once at startup.

A missing optional piece does not stop the office: the pipeline raises a clear error
only when a stage actually needs it (for example, previewing without Dokploy set up)."""
from __future__ import annotations

import logging
from pathlib import Path

from . import llm
from .checks.patch import PatchChecks
from .config import load_config
from .pipeline.ports import Deps
from .worker import make_worker

log = logging.getLogger("agents_office")


class Unconfigured:
    def __init__(self, what: str, why: str):
        self._what, self._why = what, why

    def __getattr__(self, name):
        async def refuse(*a, **k):
            raise RuntimeError(f"{self._what} is not configured: {self._why}")
        return refuse


def build_deps() -> Deps:
    cfg = load_config()
    try:
        from .connectors.dokploy import DokployDeployer
        deployer = DokployDeployer.from_config()
    except Exception as e:
        log.warning("Dokploy deployer unavailable: %s", e)
        deployer = Unconfigured("the Dokploy deployer", str(e))
    from .connectors.notify import from_config as notify_from_config
    from .connectors.web import from_config as web_from_config
    try:
        from .connectors.promote import Promoter
        promoter = Promoter.from_config()
    except Exception as e:
        log.warning("production promotion unavailable: %s", e)
        promoter = Unconfigured("production promotion", str(e))
    return Deps(chat_json=llm.ask_json, worker=make_worker(), deployer=deployer, checks=PatchChecks(),
                web=web_from_config(cfg), promoter=promoter, notifier=notify_from_config(),
                jobs_dir=Path(cfg.sandbox["jobs_dir"]))
