"""Hardened containers for build jobs. Nothing here is run by the tests; they check
the specification, and the laptop runbook (PLAN.md section 11) runs it for real.

Isolation layers (all of them, always):
  - one throwaway container per job, non-root, every capability dropped, no new
    privileges, read-only root filesystem, scratch space only in tmpfs, memory/CPU/pid caps;
  - the job network is `internal` (no route out). The only reachable hosts are the
    egress proxy (package registries, allow-listed) and the router gateway (model calls,
    which injects the router key so the key never enters the container);
  - the workspace is a COPY under data/jobs/<job>/, never a bind mount of a home
    directory; the Docker socket is never mounted;
  - the patch leaves as a git bundle made INSIDE the container, so the host never runs
    git (and so never runs repository hooks) on untrusted code.
"""
from __future__ import annotations

import asyncio
import logging
from dataclasses import dataclass
from pathlib import Path

from .config import load_config

log = logging.getLogger("agents_office.sandbox")

FORBIDDEN_MOUNT_PARTS = (".ssh", ".aws", ".config", ".gnupg", ".docker", "docker.sock", ".kube")


class UnsafeMount(ValueError):
    pass


@dataclass
class RunResult:
    exit_code: int
    logs: str
    timed_out: bool = False


def check_mount(host_path: str | Path) -> Path:
    p = Path(host_path).resolve()
    jobs = Path(load_config().sandbox["jobs_dir"]).resolve()
    if jobs not in p.parents and p != jobs:
        raise UnsafeMount(f"{p} is outside the jobs directory {jobs}")
    if any(part in p.parts for part in FORBIDDEN_MOUNT_PARTS):
        raise UnsafeMount(f"{p} looks like a credentials directory")
    return p


def container_spec(job_id: str, *, image: str, command: list[str], env: dict[str, str] | None = None) -> dict:
    """Keyword arguments for docker's `containers.run(image, command, **spec)`."""
    cfg = load_config().sandbox
    jobs_dir = Path(cfg["jobs_dir"]) / job_id
    workspace = check_mount(jobs_dir / "workspace")
    out = check_mount(jobs_dir / "out")
    proxy = cfg["proxy"]
    environment = {
        "HOME": "/home/agent", "HTTP_PROXY": proxy, "HTTPS_PROXY": proxy, "http_proxy": proxy, "https_proxy": proxy,
        "NO_PROXY": cfg.get("no_proxy", "router-gateway,localhost,127.0.0.1"),
        "no_proxy": cfg.get("no_proxy", "router-gateway,localhost,127.0.0.1"),
        "npm_config_update_notifier": "false", "CI": "1", "NEXT_TELEMETRY_DISABLED": "1",
        "PLAYWRIGHT_BROWSERS_PATH": "/ms-playwright",
        **(env or {}),
    }
    return {
        "image": image,
        "command": command,
        "name": f"ao-job-{job_id}",
        "user": cfg["user"],
        "working_dir": "/workspace",
        "environment": environment,
        "network": cfg["network"],
        "cap_drop": ["ALL"],
        "security_opt": ["no-new-privileges"],
        "read_only": True,
        "tmpfs": {"/tmp": "rw,noexec,nosuid,size=512m", "/home/agent": "rw,nosuid,size=1g"},
        "mem_limit": cfg["memory"],
        "nano_cpus": int(float(cfg["cpus"]) * 1e9),
        "pids_limit": int(cfg["pids"]),
        "volumes": {str(workspace): {"bind": "/workspace", "mode": "rw"}, str(out): {"bind": "/out", "mode": "rw"}},
        "runtime": cfg["runtime"] if cfg.get("runtime") not in (None, "", "runc") else None,
        "labels": {"agents-office.job": job_id},
        "detach": True,
        "auto_remove": False,
        "privileged": False,
    }


def assert_hardened(spec: dict) -> None:
    """Raise if a spec is missing any isolation layer. Called before every run, and by tests."""
    problems = []
    if spec.get("cap_drop") != ["ALL"]:
        problems.append("capabilities are not all dropped")
    if "no-new-privileges" not in (spec.get("security_opt") or []):
        problems.append("no-new-privileges is not set")
    if not spec.get("read_only"):
        problems.append("root filesystem is writable")
    if spec.get("privileged"):
        problems.append("container is privileged")
    if str(spec.get("user", "0")).split(":")[0] in ("0", "root", ""):
        problems.append("container runs as root")
    if spec.get("network") in (None, "", "host", "bridge"):
        problems.append(f'job network "{spec.get("network")}" is not the internal job network')
    for host in (spec.get("volumes") or {}):
        try:
            check_mount(host)
        except UnsafeMount as e:
            problems.append(str(e))
    for name in ("mem_limit", "nano_cpus", "pids_limit"):
        if not spec.get(name):
            problems.append(f"{name} is not limited")
    if problems:
        raise UnsafeMount("; ".join(problems))


def _docker():
    import docker
    return docker.from_env()


def _is_timeout(e: BaseException) -> bool:
    return any("Timeout" in k.__name__ for k in type(e).__mro__) or "timed out" in str(e).lower()


def _run_blocking(spec: dict, timeout_s: int, client=None) -> RunResult:
    client = client or _docker()
    spec = {k: v for k, v in spec.items() if v is not None}
    image, command = spec.pop("image"), spec.pop("command")
    # A run killed by a stop or a crash leaves its exited container behind; a retry of the
    # same job reuses the name, so clear the leftover first.
    try:
        client.containers.get(spec["name"]).remove(force=True)
    except Exception:  # not found (the normal case) or not removable: let run() report it
        pass
    c = client.containers.run(image, command, **spec)
    timed_out = False
    try:
        try:
            res = c.wait(timeout=timeout_s)
            code = int(res.get("StatusCode", 1))
        except Exception as e:  # only a read timeout means "ran too long"; a Docker error is an error
            if not _is_timeout(e):
                try:
                    c.kill()
                except Exception:
                    pass
                raise
            timed_out = True
            code = 124
            try:
                c.kill()
            except Exception:
                pass
        logs = c.logs(stdout=True, stderr=True, tail=2000).decode("utf-8", "replace")
    finally:
        try:
            c.remove(force=True)
        except Exception:
            log.warning("could not remove container %s", spec.get("name"))
    return RunResult(code, logs, timed_out)


def stop_job_container(job_id: str, client=None) -> bool:
    """Remove a job's container if it is running (the owner's kill switch). True if one was removed."""
    try:
        (client or _docker()).containers.get(f"ao-job-{job_id}").remove(force=True)
        return True
    except Exception:  # none running, or Docker unavailable: the kill itself must not fail
        return False


async def run_container(spec: dict, timeout_s: int, client=None) -> RunResult:
    assert_hardened(spec)
    from . import activity
    name = str(spec.get("name", ""))
    jid = name[len("ao-job-"):] if name.startswith("ao-job-") else None
    activity.emit("container", f"container {name or spec.get('image')} started", job=jid, stage="build", connector="docker")
    try:
        res = await asyncio.to_thread(_run_blocking, spec, timeout_s, client)
    except asyncio.CancelledError:
        if jid:
            await asyncio.to_thread(stop_job_container, jid, client)  # a cancelled driver must not leave the agent running
        raise
    activity.emit("container", f"container {name or spec.get('image')} exit {res.exit_code}", job=jid, stage="build",
                  connector="docker", level="info" if res.exit_code == 0 else "warn")
    return res
