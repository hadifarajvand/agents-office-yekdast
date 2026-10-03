"""Publish a job's git bundle as a branch of the private previews repository, which
Dokploy builds from. The token is limited to that one repo. Git runs with hooks off
and without reading user config; the bundle is cloned bare, so no checkout scripts run."""
from __future__ import annotations

import asyncio
import os
import subprocess
import tempfile
from pathlib import Path

from ..config import load_config


class GitPublisher:
    def _env(self, token: str) -> dict:
        return {"PATH": os.environ.get("PATH", ""), "HOME": tempfile.gettempdir(), "GIT_TERMINAL_PROMPT": "0",
                "GIT_CONFIG_NOSYSTEM": "1", "GIT_CONFIG_GLOBAL": os.devnull,
                "GIT_CONFIG_COUNT": "2",
                "GIT_CONFIG_KEY_0": "core.hooksPath", "GIT_CONFIG_VALUE_0": os.devnull,
                "GIT_CONFIG_KEY_1": "http.extraheader", "GIT_CONFIG_VALUE_1": f"Authorization: Bearer {token}"}

    def _run(self, bundle: str, branch: str, repo_url: str, token: str) -> str:
        with tempfile.TemporaryDirectory() as tmp:
            bare = str(Path(tmp) / "b.git")
            env = self._env(token)
            subprocess.run(["git", "clone", "--bare", bundle, bare], check=True, env=env, capture_output=True, timeout=120)
            subprocess.run(["git", "-C", bare, "push", "--force", repo_url, f"HEAD:refs/heads/{branch}"],
                           check=True, env=env, capture_output=True, timeout=180)
        return repo_url

    async def publish(self, bundle: str, branch: str) -> str:
        d = load_config().dokploy
        url, token = os.environ.get(d["source_repo_env"], ""), os.environ.get(d["source_token_env"], "")
        if not url or not token:
            raise RuntimeError(f'set {d["source_repo_env"]} and {d["source_token_env"]} so previews can be published')
        return await asyncio.to_thread(self._run, bundle, branch, url, token)
