"""Port of usage.mjs — the usage gauge.

Tries Claude Code's own usage endpoint with the login token Claude Code keeps on this
machine; in the container there normally is no such login, so this falls back to the
office's own count (tokens its runs have used in the current five-hour window). No
dollars anywhere.
"""
from __future__ import annotations

import json
import os
import platform
import subprocess
import time
from pathlib import Path

import httpx

ENDPOINT = "https://api.anthropic.com/api/oauth/usage"
WINDOW = 5 * 3600  # seconds


def state_file(data_dir: Path) -> Path:
    return data_dir / "usage.json"


def read_token() -> str | None:
    if platform.system() == "Darwin":
        try:
            r = subprocess.run(
                ["security", "find-generic-password", "-s", "Claude Code-credentials", "-w"],
                capture_output=True, text=True, timeout=5,
            )
            if r.returncode == 0:
                t = json.loads(r.stdout).get("claudeAiOauth", {}).get("accessToken")
                if t:
                    return t
        except Exception:
            pass
    try:
        p = Path.home() / ".claude" / ".credentials.json"
        t = json.loads(p.read_text()).get("claudeAiOauth", {}).get("accessToken")
        if t:
            return t
    except Exception:
        pass
    return None


def parse_usage(j: dict) -> dict | None:
    def pick(x):
        if not x or not isinstance(x.get("utilization"), (int, float)):
            return None
        resets_at = None
        if x.get("resets_at"):
            try:
                import datetime
                resets_at = datetime.datetime.fromisoformat(x["resets_at"].replace("Z", "+00:00")).timestamp() * 1000
            except Exception:
                resets_at = None
        return {"percent": max(0, min(100, round(x["utilization"]))), "resetsAt": resets_at}

    session = pick(j.get("five_hour"))
    week = pick(j.get("seven_day"))
    if not session and not week:
        return None
    return {"session": session, "week": week}


async def fetch_usage() -> dict:
    token = read_token()
    if not token:
        return {"ok": False, "reason": "no Claude Code login found on this machine"}
    try:
        async with httpx.AsyncClient(timeout=10.0) as client:
            r = await client.get(
                ENDPOINT,
                headers={"Authorization": f"Bearer {token}", "anthropic-beta": "oauth-2025-04-20", "Accept": "application/json"},
            )
        if r.status_code != 200:
            return {"ok": False, "reason": f"Claude's usage endpoint answered {r.status_code}"}
        u = parse_usage(r.json())
        if not u:
            return {"ok": False, "reason": "Claude's usage endpoint answered in a shape the office does not know"}
        return {"ok": True, "source": "claude", **u}
    except httpx.TimeoutException:
        return {"ok": False, "reason": "Claude's usage endpoint timed out"}
    except Exception as e:
        return {"ok": False, "reason": str(e)}


def load_state(data_dir: Path) -> dict:
    try:
        return json.loads(state_file(data_dir).read_text())
    except Exception:
        return {}


def save_state(data_dir: Path, st: dict) -> None:
    data_dir.mkdir(parents=True, exist_ok=True)
    state_file(data_dir).write_text(json.dumps(st))


def window_state(st: dict, now: float | None = None) -> dict:
    now = now if now is not None else time.time()
    started_at = st.get("startedAt")
    if not started_at or now - started_at >= WINDOW:
        return {"startedAt": None, "tokens": 0, "runs": 0}
    return {"startedAt": started_at, "tokens": st.get("tokens", 0), "runs": st.get("runs", 0)}


def record(st: dict, usage: dict | None, now: float | None = None) -> dict:
    now = now if now is not None else time.time()
    w = window_state(st, now)
    if not w["startedAt"]:
        w["startedAt"] = now
    u = usage or {}
    w["tokens"] += (u.get("input_tokens", 0) + u.get("output_tokens", 0)
                     + u.get("cache_creation_input_tokens", 0) + u.get("cache_read_input_tokens", 0))
    w["runs"] += 1
    return w


def fallback(st: dict, now: float | None = None) -> dict:
    now = now if now is not None else time.time()
    w = window_state(st, now)
    return {
        "ok": True, "source": "office",
        "window": {
            "tokens": w["tokens"], "runs": w["runs"], "startedAt": w["startedAt"],
            "resetsAt": (w["startedAt"] + WINDOW) if w["startedAt"] else None,
        },
    }
