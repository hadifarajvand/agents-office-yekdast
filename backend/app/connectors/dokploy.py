"""Deploys previews to the owner's Dokploy through its MCP server.

Rules built in:
  - only allow-listed tools can be called (config.dokploy.tool_allowlist), and anything
    destructive or administrative is refused even if listed (guard.HARD_DENY);
  - every call is audited before it runs;
  - a preview starts PRIVATE: the app is created and deployed with no domain;
  - basic auth is configured on the app at deploy time; credentials are written to a 0600
    file next to the job (never to logs, evidence or the database);
  - exposure adds one domain under the preview domain, then the caller probes it.

UNVERIFIED until runbook S5: the tool names and argument shapes below follow the Dokploy
API as documented for @dokploy/mcp at the time of writing; they live in TOOLS and the
_args_* helpers so a correction touches one place.
"""
from __future__ import annotations

import json
import os
import secrets
from pathlib import Path
from typing import Any

import httpx

from ..config import load_config
from .git_publish import GitPublisher
from .guard import Guard
from .mcp_client import McpSession

TOOLS = {
    "projects": "project-all", "create_app": "application-create", "git": "application-saveGitProvider",
    "build": "application-saveBuildType", "deploy": "application-deploy", "stop": "application-stop",
    "auth": "security-create", "domain": "domain-create",
}


def _unwrap(res: Any) -> Any:
    """MCP tools may return JSON text, a dict, or a list of content blocks."""
    if isinstance(res, str):
        try:
            return json.loads(res)
        except ValueError:
            return res
    if isinstance(res, list) and res and isinstance(res[0], dict) and "text" in res[0]:
        return _unwrap(res[0]["text"])
    return res


class DokployDeployer:
    def __init__(self, guard: Guard, publisher: GitPublisher | None = None, http: httpx.AsyncClient | None = None):
        self.guard, self.publisher, self._http = guard, publisher or GitPublisher(), http

    @classmethod
    def from_config(cls) -> "DokployDeployer":
        cfg = load_config().dokploy
        url, key = os.environ.get(cfg["url_env"], ""), os.environ.get(cfg["api_key_env"], "")
        if not url or not key:
            raise RuntimeError(f'set {cfg["url_env"]} and {cfg["api_key_env"]} to use Dokploy')
        cmd = cfg["command"]
        session = McpSession("dokploy", {"transport": "stdio", "command": cmd[0], "args": cmd[1:],
                                         "env": {"DOKPLOY_URL": url, "DOKPLOY_API_KEY": key,
                                                 "PATH": os.environ.get("PATH", "")}})
        return cls(Guard("dokploy", cfg["tool_allowlist"], session.invoke))

    # ----- helpers -----
    def _cfg(self) -> dict:
        return load_config().dokploy

    def _creds_file(self, job: dict) -> Path:
        d = Path(load_config().sandbox["jobs_dir"]) / job["id"]
        d.mkdir(parents=True, exist_ok=True)
        return d / "preview-credentials.txt"

    async def _environment_id(self) -> str:
        projects = _unwrap(await self.guard.call(TOOLS["projects"], {}))
        for p in projects if isinstance(projects, list) else []:
            if p.get("name") == self._cfg()["project"]:
                envs = p.get("environments") or []
                if envs:
                    return envs[0]["environmentId"]
        raise RuntimeError(f'Dokploy has no project named "{self._cfg()["project"]}" (create it once, by hand)')

    # ----- Deployer protocol -----
    async def deploy_preview(self, job: dict, patch_path: str) -> dict:
        branch = f'preview/{job["id"]}'
        repo = await self.publisher.publish(patch_path, branch)
        env_id = await self._environment_id()
        app = _unwrap(await self.guard.call(TOOLS["create_app"], {"name": f'preview-{job["id"]}', "environmentId": env_id}))
        app_id = app.get("applicationId") if isinstance(app, dict) else None
        if not app_id:
            raise RuntimeError("Dokploy did not return an application id")
        await self.guard.call(TOOLS["git"], {"applicationId": app_id, "customGitUrl": repo, "customGitBranch": branch,
                                             "customGitBuildPath": "/"})
        # The template ships a Dockerfile; building it is deterministic, unlike nixpacks' guess.
        await self.guard.call(TOOLS["build"], {"applicationId": app_id, "buildType": "dockerfile",
                                               "dockerfile": "Dockerfile", "dockerContextPath": "", "dockerBuildStage": ""})
        user, password = "preview", secrets.token_urlsafe(18)
        await self.guard.call(TOOLS["auth"], {"applicationId": app_id, "username": user, "password": password})
        f = self._creds_file(job)
        f.write_text(f"user: {user}\npassword: {password}\n")
        os.chmod(f, 0o600)
        await self.guard.call(TOOLS["deploy"], {"applicationId": app_id})
        return {"app_id": app_id, "internal_url": f"app:{app_id}", "auth_user": user, "branch": branch}

    async def auth_configured(self, preview: dict) -> dict:
        ok = bool(preview.get("auth_user")) and bool(preview.get("app_id"))
        return {"ok": ok, "detail": "basic auth was set when the app was created" if ok else "no auth layer recorded"}

    async def apply_exposure(self, job: dict, preview: dict, tier: int) -> dict:
        d = self._cfg()
        base = os.environ.get(d["preview_domain_env"], "")
        if not base:
            raise RuntimeError(f'set {d["preview_domain_env"]} to expose previews')
        host = f'{job["id"]}.{base}'
        await self.guard.call(TOOLS["domain"], {"host": host, "applicationId": preview["app_id"], "https": True,
                                                "port": int(d.get("app_port", 3000)), "certificateType": "letsencrypt",
                                                "domainType": "application"})
        return {"url": f"https://{host}"}

    async def probe_unauthenticated(self, preview: dict) -> dict:
        url = preview.get("url")
        if not url:
            return {"status": 0, "ok": False}
        client = self._http or httpx.AsyncClient(timeout=20, follow_redirects=False)
        try:
            r = await client.get(url)
            return {"status": r.status_code, "ok": r.status_code in (401, 403)}
        except httpx.HTTPError:
            return {"status": 0, "ok": False}
        finally:
            if self._http is None:
                await client.aclose()

    async def stop(self, job: dict, preview: dict) -> None:
        if preview.get("app_id"):
            await self.guard.call(TOOLS["stop"], {"applicationId": preview["app_id"]})
