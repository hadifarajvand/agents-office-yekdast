"""Read-only integrity check over the stored task rows.

The task lists the owner sees are built in the browser from `GET /api/tasks`; when a count looks wrong
(the "65 tasks" question) this says which rows disagree with the rest of the system and why. It reports
only: it never edits, deletes or re-states a row, so history stays as it was written. What to do with a
finding is the owner's call (MASTER_PLAN Part G, S3).
"""
from __future__ import annotations

from collections import Counter

from . import db

STATES = ("next", "doing", "waiting", "done", "sched")
REQUIRED = ("id", "dept", "agent")
SHOWN_IDS = 10
ERRORS = {"bad_state", "missing_field"}


def _finding(code: str, detail: str, ids: list[str]) -> dict:
    return {"code": code, "severity": "error" if code in ERRORS else "warn", "detail": detail,
            "count": len(ids), "ids": ids[:SHOWN_IDS]}


def check(tasks: list[dict], jobs: list[dict], seat_ids: set[str]) -> dict:
    """Compare task rows with the jobs and the seat roster. Pure: inputs are never modified."""
    status = {j.get("id"): j.get("status") for j in jobs}
    by_state = Counter(str(t.get("state") or "(none)") for t in tasks)
    found: dict[str, list[str]] = {}

    def flag(code: str, t: dict):
        found.setdefault(code, []).append(str(t.get("id", "?")))

    dup_seen: set[tuple] = set()
    former = failed = 0
    for t in sorted(tasks, key=lambda x: str(x.get("id", ""))):
        if t.get("state") not in STATES:
            flag("bad_state", t)
        if any(not t.get(k) for k in REQUIRED):
            flag("missing_field", t)
        agent = t.get("agent")
        if agent and agent not in seat_ids:
            former += 1
            flag("former_seat", t)
        if t.get("state") == "done" and t.get("error"):
            failed += 1
            if not str(t.get("result") or "").strip():
                flag("failed_without_reason", t)
        if not t.get("pipeline"):
            continue
        if t.get("jobId") not in status:
            flag("orphan_pipeline_row", t)
        elif t.get("state") == "doing" and status[t["jobId"]] != "running":
            flag("stale_doing_row", t)
        if "attempt" in t:  # rows written before attempts existed cannot be told apart, so they are never compared
            key = (t.get("jobId"), str(t.get("id", "")).rsplit("-", 1)[0], t.get("parks", 0))
            if key in dup_seen:
                flag("duplicate_pipeline_row", t)
            dup_seen.add(key)

    detail = {
        "bad_state": f"state is not one of {', '.join(STATES)}",
        "missing_field": f"a row lacks one of {', '.join(REQUIRED)}",
        "former_seat": "the row's agent is not a seat in the roster; the UI hides it as a former seat (history kept)",
        "failed_without_reason": "a failed row (done with error) carries no result text",
        "orphan_pipeline_row": "a pipeline row points at a job that no longer exists",
        "stale_doing_row": "a pipeline row is still doing but its job is not running",
        "duplicate_pipeline_row": "the same stage, seat and attempt was written twice for one park count",
    }
    findings = [_finding(code, detail[code], ids) for code, ids in sorted(found.items())]
    return {"ok": not any(f["severity"] == "error" for f in findings), "total": len(tasks),
            "byState": dict(by_state), "failed": failed, "hiddenFormerSeat": former, "visible": len(tasks) - former,
            "findings": findings}


def summary(report: dict) -> str:
    bits = ", ".join(f'{f["code"]}={f["count"]}' for f in report["findings"]) or "no findings"
    return f'{report["total"]} task row(s), {report["failed"]} failed, {report["hiddenFormerSeat"]} of a former seat: {bits}'


async def run(seat_ids: set[str]) -> dict:
    return check(await db.list_tasks(), await db.list_jobs(), seat_ids)
