"""Interfaces the pipeline depends on. Real adapters live in app/worker and
app/connectors; tests use fakes. Nothing in the pipeline imports a concrete adapter."""
from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Awaitable, Callable, Protocol, TypedDict


class BuildResult(TypedDict, total=False):
    patch_path: str        # git bundle or unified diff produced by the worker
    log_path: str
    tokens: int
    usd: float
    models_seen: list      # router model ids that actually answered
    exit_state: str        # ok | failed | timeout


class BuildWorker(Protocol):
    async def run(self, job_dir: Path, brief: dict, limits: dict) -> BuildResult: ...


class Deployer(Protocol):
    async def deploy_preview(self, job: dict, patch_path: str) -> dict:
        """Create/refresh the app in the previews project. Private (Tier 0): no public route.
        Returns {app_id, internal_url}."""
    async def auth_configured(self, preview: dict) -> dict:
        """Is the authentication layer (basic auth / access policy) configured on the app?
        Returns {ok:bool, detail:str}. A private preview has no public route to probe yet,
        so this configuration check is the evidence the exposure gate can rely on."""
    async def apply_exposure(self, job: dict, preview: dict, tier: int) -> dict:
        """Add the public route for Tier 1 (with auth) or Tier 2, in one step. Returns {url}."""
    async def probe_unauthenticated(self, preview: dict) -> dict:
        """One request with no credentials to the PUBLIC url, made right after apply_exposure.
        Returns {status:int, ok:bool}; ok means access was refused (401/403)."""
    async def stop(self, job: dict, preview: dict) -> None: ...


class Checks(Protocol):
    async def scan(self, patch_path: str) -> list[dict]:
        """Deterministic checks over the patch: [{name, ok, detail}]."""


ChatJson = Callable[..., Awaitable[dict]]  # async (system, user, *, role) -> dict


@dataclass
class Deps:
    chat_json: ChatJson
    worker: BuildWorker | None = None
    deployer: Deployer | None = None
    checks: Checks | None = None
    web: object | None = None      # connectors.web.WebTool (research stage only)
    jobs_dir: Path = field(default_factory=lambda: Path("data/jobs"))


_deps: Deps | None = None


def set_deps(d: Deps | None) -> None:
    global _deps
    _deps = d


def get_deps() -> Deps:
    if _deps is None:
        raise RuntimeError("pipeline dependencies are not configured (see app/pipeline/ports.py)")
    return _deps
