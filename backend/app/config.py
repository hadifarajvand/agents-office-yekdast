"""Office configuration: office.config.json <- office.config.local.json <- environment.

Every section has a default here, so a missing or partial config file still yields a
complete, typed Config. Unknown top-level keys are reported in `Config.problems`
rather than failing startup. Secrets are never stored in these files; the config only
names the environment variable that holds each secret (`*_env` keys).
"""
from __future__ import annotations

import copy
import json
import os
from dataclasses import dataclass, field
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]

# Pipeline stage -> (owning department, approving lead seat). The building
# department never appears as an approver of "exposure" (see pipeline/exposure.py).
DEFAULT_STAGES = [
    {"name": "intake", "dept": "exec", "lead": "olead", "label": "Intake"},
    {"name": "verify", "dept": "exec", "lead": "olead", "label": "Verify"},
    {"name": "scope", "dept": "engineering", "lead": "dlead", "label": "Scope"},
    {"name": "build", "dept": "engineering", "lead": "dlead", "label": "Build"},
    {"name": "security", "dept": "secdata", "lead": "comply", "label": "Security review"},
    {"name": "preview", "dept": "devops", "lead": "qa", "label": "Preview deploy"},
    {"name": "exposure", "dept": "secdata", "lead": "comply", "label": "Exposure"},
    {"name": "handoff", "dept": "revenue", "lead": "lexi", "label": "Handoff"},
]

DEFAULTS: dict = {
    "name": "Agents Office",
    "brain": "./brain",
    "port": 4520,
    "model": "haiku",
    "mcp": {"allow": [], "deny": [], "departments": {}},
    "tools": {"web": False},
    # Model access through the local 9router proxy. base_url has no trailing /v1;
    # the client adds the path its format needs.
    "router": {
        "base_url": "http://host.docker.internal:20128",
        "api_key_env": "ROUTER_API_KEY",
        "format": "openai",  # "openai" (/v1/chat/completions) or "anthropic" (/v1/messages)
        "timeout_s": 120,
        # Office model keys (task/agent/routine menus) -> router model ids.
        "models": {
            "haiku": "cc/claude-haiku-4-5-20251001",
            "sonnet": "cc/claude-sonnet-5",
            "opus": "cc/claude-opus-5",
            "fable": "cc/claude-fable-5-1",
        },
    },
    # Pinned model per pipeline role (owner decision 2026-10-03: Haiku builds,
    # free-tier GLM for research, drafts, tests and reviews).
    "roles": {
        "builder": "cc/claude-haiku-4-5-20251001",
        "router": "kr/glm-5",
        "research": "kr/glm-5",
        "drafts": "kr/glm-5",
        "tests": "kr/glm-5",
        "lead_review": "kr/glm-5",
        "chat": "kr/glm-5",
    },
    "budget": {"usd_per_job": 1.0, "usd_per_1k_tokens": {"default": 0.0}},
    "pipeline": {"stages": DEFAULT_STAGES, "deadline_days": 3, "max_review_loops": 2,
                 "owner_gates": ["verify", "handoff"]},  # stages that also need the owner's click
    # Two keys for a gated (Tier 1) preview: an independent security verdict and
    # commercial consent. Neither may be the building department's lead.
    "exposure": {"tier1_owner_clicks": 3, "preview_ttl_days": 7,
                 "keys": {"security": "comply", "commercial": "olead"}},
    "worker": {"kind": "fake", "timeout_minutes": 180, "images": {
        "claude_code": "agents-office/worker-node:latest",
        "openhands": "agents-office/worker-openhands:latest",
        "mini_swe": "agents-office/worker-node:latest",
    }},
    "sandbox": {
        "runtime": "runc",  # set "runsc" for gVisor on a Linux host
        "network": "ao-internal",
        "proxy": "http://egress:3128",              # squid: package registries only
        "router_gateway": "http://router-gateway:8080",  # nginx: adds the router key, forwards to 9router
        "no_proxy": "router-gateway,localhost,127.0.0.1",
        "cpus": 2.0,
        "memory": "4g",
        "pids": 512,
        "user": "1000:1000",
        "jobs_dir": "./data/jobs",
    },
    "dokploy": {
        "url_env": "DOKPLOY_URL",
        "api_key_env": "DOKPLOY_API_KEY",
        "transport": "stdio",
        "command": ["npx", "-y", "@dokploy/mcp"],  # official server (Apache-2.0), ~508 tools, no read-only mode
        # Exact tool names must be confirmed against the installed server version (laptop runbook S5);
        # any tool annotated destructiveHint is refused even if listed here.
        "project": "previews",
        "preview_domain_env": "DOKPLOY_PREVIEW_DOMAIN",  # e.g. preview.example.com; one host per job below it
        "source_repo_env": "PREVIEW_REPO_URL",           # private git repo Dokploy builds previews from
        "source_token_env": "PREVIEW_REPO_TOKEN",        # token limited to THAT repo only (write)
        "app_port": 3000,
        "tool_allowlist": [
            "project-one", "project-all", "application-one", "application-create",
            "application-update", "application-saveGitProvider", "application-saveBuildType",
            "application-deploy", "application-redeploy", "application-stop",
            "security-create", "domain-create", "domain-byApplicationId",
        ],
    },
    "github": {"token_env": "GITHUB_TOKEN", "url": "https://api.githubcopilot.com/mcp/readonly", "readonly": True},
    "api": {"token_env": "AO_API_TOKEN", "allowed_hosts": ["localhost", "127.0.0.1", "testserver"]},
}

KNOWN_KEYS = set(DEFAULTS) | {"_comment"}


def _read_json(path: Path) -> dict:
    try:
        return json.loads(path.read_text())
    except FileNotFoundError:
        return {}
    except json.JSONDecodeError as e:
        return {"__error": f"{path.name}: not valid JSON ({e})"}


def _merge(base: dict, over: dict) -> dict:
    out = copy.deepcopy(base)
    for k, v in (over or {}).items():
        if isinstance(v, dict) and isinstance(out.get(k), dict):
            out[k] = _merge(out[k], v)
        else:
            out[k] = copy.deepcopy(v)
    return out


@dataclass
class Config:
    name: str
    brain: str
    port: int
    model: str
    mcp: dict
    tools: dict
    brain_path: Path
    router: dict = field(default_factory=dict)
    roles: dict = field(default_factory=dict)
    budget: dict = field(default_factory=dict)
    pipeline: dict = field(default_factory=dict)
    exposure: dict = field(default_factory=dict)
    worker: dict = field(default_factory=dict)
    sandbox: dict = field(default_factory=dict)
    dokploy: dict = field(default_factory=dict)
    github: dict = field(default_factory=dict)
    api: dict = field(default_factory=dict)
    problems: list = field(default_factory=list)

    def secret(self, section: str, key: str = "api_key_env") -> str:
        """Read a secret from the environment variable a section names."""
        env_name = (getattr(self, section) or {}).get(key) or ""
        return os.environ.get(env_name, "") if env_name else ""


_ENV_KEYS = ("AO_NAME", "AO_BRAIN", "PORT", "AO_MODEL", "ROUTER_BASE_URL", "ROUTER_FORMAT", "AO_WORKER")
_cache: dict = {"key": None, "cfg": None}


def _cache_key() -> tuple:
    def mt(p: Path):
        try:
            return p.stat().st_mtime_ns
        except OSError:
            return None
    return (mt(ROOT / "office.config.json"), mt(ROOT / "office.config.local.json"),
            tuple(os.environ.get(k) for k in _ENV_KEYS))


def load_config() -> Config:
    """The merged config. Cached until a config file or a relevant environment
    variable changes, so every module sees one object (tests clear it with
    `load_config.cache_clear()`)."""
    key = _cache_key()
    if _cache["key"] != key or _cache["cfg"] is None:
        _cache.update(key=key, cfg=_load())
    return _cache["cfg"]


def _clear() -> None:
    _cache.update(key=None, cfg=None)


load_config_cache_clear = _clear


def _load() -> Config:
    problems: list[str] = []
    base = _read_json(ROOT / "office.config.json")
    local = _read_json(ROOT / "office.config.local.json")
    for doc in (base, local):
        if "__error" in doc:
            problems.append(doc.pop("__error"))
        for k in doc:
            if k not in KNOWN_KEYS:
                problems.append(f'unknown config key "{k}" — ignored')
    merged = _merge(_merge(DEFAULTS, base), local)

    merged["name"] = os.environ.get("AO_NAME", merged["name"])
    merged["brain"] = os.environ.get("AO_BRAIN", merged["brain"])
    merged["port"] = int(os.environ.get("PORT", merged["port"]))
    merged["model"] = os.environ.get("AO_MODEL", merged["model"])
    if os.environ.get("ROUTER_BASE_URL"):
        merged["router"]["base_url"] = os.environ["ROUTER_BASE_URL"]
    if os.environ.get("ROUTER_FORMAT"):
        merged["router"]["format"] = os.environ["ROUTER_FORMAT"]
    if os.environ.get("AO_WORKER"):
        merged["worker"]["kind"] = os.environ["AO_WORKER"]

    brain_path = Path(merged["brain"])
    if not brain_path.is_absolute():
        brain_path = (ROOT / brain_path).resolve()
    jobs_dir = Path(merged["sandbox"]["jobs_dir"])
    if not jobs_dir.is_absolute():
        merged["sandbox"]["jobs_dir"] = str((ROOT / jobs_dir).resolve())

    return Config(
        name=merged["name"], brain=merged["brain"], port=merged["port"], model=merged["model"],
        mcp=merged["mcp"], tools=merged["tools"], brain_path=brain_path,
        router=merged["router"], roles=merged["roles"], budget=merged["budget"],
        pipeline=merged["pipeline"], exposure=merged["exposure"], worker=merged["worker"],
        sandbox=merged["sandbox"], dokploy=merged["dokploy"], github=merged["github"],
        api=merged["api"], problems=problems,
    )


load_config.cache_clear = _clear  # type: ignore[attr-defined]
