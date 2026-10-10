"""Promote a finished job to production: the OWNER's button, never an agent's.

Nothing in the graph, the bench, the consults or any agent tool list can reach this module; only
the owner's HTTP endpoint (pipeline/api.py, /promote) calls it. Two steps, so production never
starts half-configured:

  prepare  create a private GitHub repo for the product and push the reviewed build to main;
           create the app in the Dokploy "production" project (Dockerfile build, the owner's
           domain with HTTPS). Nothing is deployed yet. Returns the environment variable NAMES
           the app needs (from its .env.example), which the owner sets in Dokploy.
  deploy   after the owner confirms the variables are set: deploy, then probe
           https://<domain>/healthz. A failed probe is reported, not hidden; the owner decides.

UNVERIFIED until runbook S5: Dokploy tool names/arguments (same TOOLS map as previews) and how
Dokploy authenticates to a private GitHub repo (customGitUrl with a token, or a GitHub provider).
"""
from __future__ import annotations

import asyncio
import os
import re
import tarfile
from pathlib import Path

import httpx

from .. import db
from ..config import load_config
from .dokploy import TOOLS, DokployDeployer, _unwrap
from .git_publish import GitPublisher

HOST = re.compile(r"^(?=.{4,253}$)([a-z0-9]([a-z0-9-]{0,61}[a-z0-9])?\.)+[a-z]{2,63}$")


def slug(title: str, job_id: str) -> str:
    s = re.sub(r"[^a-z0-9]+", "-", title.lower()).strip("-")[:40] or "app"
    return f"{s}-{job_id[:6]}"


def env_names(out_dir: str | Path) -> list[str]:
    """Variable NAMES from the build's .env.example (read from the scanned tree, never executed)."""
    tar = Path(out_dir) / "tree.tar.gz"
    if not tar.exists():
        return []
    try:
        with tarfile.open(tar, "r:gz") as t:
            for m in t.getmembers():
                if m.isfile() and m.name.removeprefix("./") == ".env.example" and m.size < 50_000:
                    text = t.extractfile(m).read().decode("utf-8", "replace")
                    return sorted({ln.split("=", 1)[0].strip() for ln in text.splitlines()
                                   if re.match(r"^\s*[A-Z][A-Z0-9_]*\s*=", ln)})
    except (tarfile.TarError, OSError):
        return []
    return []


class RepoCreator:
    """Creates a private repo under the configured owner and pushes the job's git bundle to main."""

    def __init__(self, owner: str, token: str, publisher: GitPublisher | None = None, http: httpx.AsyncClient | None = None):
        self.owner, self.token, self.publisher, self._http = owner, token, publisher or GitPublisher(), http

    async def create_and_push(self, name: str, bundle: str) -> str:
        await db.audit("owner", "exec", "github", "repo-create", f"{self.owner}/{name}", True, "owner promote")
        h = {"Authorization": f"Bearer {self.token}", "Accept": "application/vnd.github+json"}
        client = self._http or httpx.AsyncClient(base_url="https://api.github.com", timeout=30, headers=h)
        try:
            me = (await client.get("/user")).json().get("login", "")
            path = "/user/repos" if me.lower() == self.owner.lower() else f"/orgs/{self.owner}/repos"
            r = await client.post(path, json={"name": name, "private": True, "auto_init": False})
            if r.status_code not in (201, 422):  # 422 = it exists already (a second prepare)
                raise RuntimeError(f"GitHub refused to create {self.owner}/{name}: HTTP {r.status_code}")
        finally:
            if self._http is None:
                await client.aclose()
        url = f"https://github.com/{self.owner}/{name}.git"
        await asyncio.to_thread(self.publisher._run, bundle, "main", url, self.token)
        return url


class Promoter:
    def __init__(self, deployer: DokployDeployer, repos: RepoCreator, http: httpx.AsyncClient | None = None):
        self.deployer, self.repos, self._http = deployer, repos, http

    @classmethod
    def from_config(cls) -> "Promoter":
        p = load_config().production
        owner, token = os.environ.get(p["github_owner_env"], ""), os.environ.get(p["token_env"], "")
        if not owner or not token:
            raise RuntimeError(f'set {p["github_owner_env"]} and {p["token_env"]} to promote products')
        return cls(DokployDeployer.from_config(), RepoCreator(owner, token))

    async def prepare(self, job: dict, bundle: str, domain: str) -> dict:
        name = slug(job["title"], job["id"])
        repo = await self.repos.create_and_push(name, bundle)
        g = self.deployer.guard
        env_id = await self.deployer._environment_id(load_config().production["project"])
        app = _unwrap(await g.call(TOOLS["create_app"], {"name": f"prod-{name}", "environmentId": env_id}))
        app_id = app.get("applicationId") if isinstance(app, dict) else None
        if not app_id:
            raise RuntimeError("Dokploy did not return an application id")
        await g.call(TOOLS["git"], {"applicationId": app_id, "customGitUrl": repo, "customGitBranch": "main", "customGitBuildPath": "/"})
        await g.call(TOOLS["build"], {"applicationId": app_id, "buildType": "dockerfile", "dockerfile": "Dockerfile",
                                      "dockerContextPath": "", "dockerBuildStage": ""})
        await g.call(TOOLS["domain"], {"host": domain, "applicationId": app_id, "https": True, "port": 3000,
                                       "certificateType": "letsencrypt", "domainType": "application"})
        return {"repo": repo, "app_id": app_id, "url": f"https://{domain}"}

    async def deploy(self, prod: dict) -> dict:
        await self.deployer.guard.call(TOOLS["deploy"], {"applicationId": prod["app_id"]})
        return await self.probe(prod["url"])

    async def probe(self, url: str, tries: int = 30, wait_s: float = 10.0) -> dict:
        client = self._http or httpx.AsyncClient(timeout=15, follow_redirects=True)
        status = 0
        try:
            for _ in range(tries):
                try:
                    status = (await client.get(url.rstrip("/") + "/healthz")).status_code
                    if status == 200:
                        return {"ok": True, "status": 200}
                except httpx.HTTPError:
                    pass
                await asyncio.sleep(wait_s)
        finally:
            if self._http is None:
                await client.aclose()
        return {"ok": False, "status": status}


def checklist(job: dict, evidence: list[dict]) -> list[dict]:
    """What must be true before the owner may promote. Every item is computed from the record."""
    def latest(stage: str) -> list[dict]:
        rows = [e for e in evidence if e["stage"] == stage and e["kind"] == "check"]
        top = max((int((e.get("body") or {}).get("attempt", 0)) for e in rows), default=0)
        return [e for e in rows if int((e.get("body") or {}).get("attempt", 0)) == top]

    build = latest("build")
    real = [e for e in build if not e["title"].startswith("fake worker")]
    sec = latest("security")
    prev = job.get("preview") or {}
    return [
        {"name": "the build lane finished: every gate passed", "ok": job.get("lane", "build") == "build" and job.get("status") == "done"},
        {"name": "the app was built, tested and started by a real worker, all green",
         "ok": bool(real) and all(e.get("ok") for e in build), "detail": f"{sum(1 for e in build if e.get('ok'))}/{len(build)} checks green"},
        {"name": "the security checks passed", "ok": bool(sec) and all(e.get("ok") for e in sec), "detail": f"{len(sec)} checks"},
        {"name": "the production repo is configured (PRODUCT_GITHUB_OWNER and PRODUCT_REPO_TOKEN are set)",
         "ok": bool(os.environ.get("PRODUCT_GITHUB_OWNER")) and bool(os.environ.get("PRODUCT_REPO_TOKEN"))},
        {"name": "a preview was deployed and reviewed", "ok": bool(prev.get("app_id")) and not prev.get("stopped")},
    ]
