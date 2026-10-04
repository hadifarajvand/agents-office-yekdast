"""Reads /out/checks.json, the results of infra/sandbox/run-checks.mjs: the job container
installed, built, tested and started the app and probed it. The host only parses the
file (size-capped, fields validated); it never runs the app's code.

Missing or unreadable results count as a failed check: a build is only green when the
container proved it."""
from __future__ import annotations

import json
from pathlib import Path

MAX_BYTES = 400_000
REQUIRED = ("dependencies install", "unit tests pass (npm test)", "the app starts and /healthz answers 200")


def read_checks(out_dir: str | Path) -> list[dict]:
    f = Path(out_dir) / "checks.json"
    if not f.exists():
        return [{"name": "the app was installed, built, tested and started", "ok": False,
                 "detail": "no checks.json: the job container did not run the checks"}]
    try:
        raw = f.read_bytes()[:MAX_BYTES]
        data = json.loads(raw)
    except (OSError, ValueError) as e:
        return [{"name": "check results are readable", "ok": False, "detail": f"checks.json: {type(e).__name__}"}]
    out = []
    for r in data if isinstance(data, list) else []:
        if isinstance(r, dict) and r.get("name"):
            out.append({"name": str(r["name"])[:120], "ok": r.get("ok") is True,
                        "detail": str(r.get("detail", ""))[-2500:], "ms": int(r.get("ms") or 0)})
    names = {r["name"] for r in out}
    stopped_early = any(not r["ok"] for r in out)
    if not stopped_early:  # a run that "passed" must have done every required step
        for need in REQUIRED:
            if need not in names:
                out.append({"name": need, "ok": False, "detail": "this step did not run"})
    return out or [{"name": "check results are present", "ok": False, "detail": "checks.json is empty"}]
