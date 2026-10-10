"""Pipeline work shown as tasks, so each department and seat is visibly doing something.

Every stage, seat finding and lead review writes one task row (state doing, then done) that the
office UI already renders as an agent card. These rows are display only: `by` is "pipeline", the
run/revise endpoints refuse them, and nothing here can change a verdict or a stage. A failure to
write one is logged and swallowed; the pipeline never waits on or fails because of its own display.
"""
from __future__ import annotations

import logging
import time

from .. import db
from ..config import load_config

log = logging.getLogger("ao.activity")


def _now() -> int:
    return int(time.time() * 1000)


def stage_cfg(stage: str) -> dict:
    return next((s for s in load_config().pipeline.get("stages", []) if s["name"] == stage), {})


def dept_of_seat(seat: str, stage: str) -> str:
    """The department a seat belongs to: its own lead row if it leads a stage, else the stage's."""
    stages = load_config().pipeline.get("stages", [])
    own = next((s["dept"] for s in stages if s.get("lead") == seat), None)
    return own or stage_cfg(stage).get("dept", "exec")


# What each stage actually does, shown as the card's plan so the UI says more than a stage name.
STAGE_PLAN = {
    "intake": ["Read the client request", "Write the job record (title, lane, brief)"],
    "verify": ["Ask the model the computed checks: real deposit, clear scope, price fits effort, realistic deadline",
               "Computed rubric decides the verdict; the owner approves at the gate"],
    "scope": ["Turn the brief into tasks, stack and acceptance criteria", "Write TASK.md for the builder"],
    "build": ["Start the sandboxed worker container from the template", "Claude Code builds and runs tests",
              "Container checks (build, start, /healthz, unit, e2e) decide pass or fail"],
    "security": ["Scan dependencies and code", "Compliance lead reviews the evidence"],
    "preview": ["Deploy a preview build", "QA lead reviews the preview"],
    "exposure": ["Check what the preview would expose", "Compliance lead approves exposure"],
    "handoff": ["Prepare the hand-off summary", "Owner gate: Promote is the owner's action"],
    "research": ["Score the market rubric", "Owner gate"],
}


def _brief(job: dict) -> str:
    b = job.get("brief") or job.get("request") or ""
    return (b if isinstance(b, str) else str(b))[:400]


async def start(job: dict, stage: str, seat: str, what: str, *, dept: str | None = None, key: str = "",
                attempt: int | None = None) -> str | None:
    """Open a "doing" task for `seat` and return its id (None if it could not be written).

    `attempt` is the review-loop round (the same number the stage's evidence carries); `parks` is how
    many times the job had parked when the row opened, so a retry after a park is not mistaken for a duplicate."""
    try:
        t = _now()
        tag = f"-a{attempt}" if attempt is not None else ""
        tid = f'pl-{job["id"]}-{stage}-{seat}{("-" + key) if key else ""}{tag}-{t}'
        title = f'{job.get("title", "job")} — {what}'
        await db.save_task({"id": tid, "dept": dept or dept_of_seat(seat, stage), "agent": seat, "by": "pipeline",
                            "pipeline": True, "jobId": job["id"], "stage": stage, "state": "doing", "title": title,
                            "text": (_brief(job) or title), "plan": list(STAGE_PLAN.get(stage, [])) if key != "review" else
                            [f"Read the {stage} evidence", "Return PASS or FAIL with reasons"],
                            "lane": job.get("lane", ""), "needsOk": False, "createdAt": t, "addedAt": t, "startedAt": t, "runs": 0,
                            **({"attempt": attempt, "parks": int(job.get("parkCount", 0))} if attempt is not None else {})})
        return tid
    except Exception:  # display only
        log.exception("activity.start failed")
        return None


async def finish(tid: str | None, ok: bool = True, result: str = "") -> None:
    if not tid:
        return
    try:
        task = await db.get_task(tid)
        if not task:
            return
        now = _now()
        secs = max(0, (now - int(task.get("startedAt", now))) // 1000)
        took = f"{secs // 60} min {secs % 60} s" if secs >= 60 else f"{secs} s"
        task.update(state="done", doneAt=now, durationSec=secs, error=not ok,
                    result=f'{(result or ("done" if ok else "failed"))[:1400]} (took {took})')
        await db.save_task(task)
    except Exception:
        log.exception("activity.finish failed")
