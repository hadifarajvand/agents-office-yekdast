"""Jobs API: create jobs, read them, record the owner's decisions, kill.

Only the owner acts through HTTP. Lead approvals are written by the graph itself
(leads.review -> db.record_approval); an HTTP request can never record a lead's PASS.
"""
from __future__ import annotations

import asyncio
import logging

from fastapi import APIRouter, Request
from fastapi.responses import JSONResponse
from langgraph.types import Command

from .. import db
from ..config import load_config
from . import exposure as exp
from . import jobs
from .graph import compiled

log = logging.getLogger("agents_office.pipeline")
router = APIRouter(prefix="/api/jobs")

_running: set[asyncio.Task] = set()


def _spawn(coro):
    t = asyncio.create_task(coro)
    _running.add(t)
    t.add_done_callback(_running.discard)
    return t


def thread(job_id: str) -> dict:
    return {"configurable": {"thread_id": f"job-{job_id}"}, "recursion_limit": 200}


async def _drive(job_id: str, payload) -> None:
    """Run (or resume) the graph until it finishes or pauses at the next interrupt."""
    try:
        await compiled().ainvoke(payload, config=thread(job_id))
    except Exception:
        log.exception("job %s crashed", job_id)
        try:
            await jobs.touch(job_id, status="failed", parkReason="the pipeline crashed — see the server log")
        except KeyError:
            pass


async def _view(job_id: str) -> dict | None:
    job = await db.get_job(job_id)
    if job is None:
        return None
    return jobs.public(job, await db.list_approvals(job_id), await db.list_evidence(job_id))


async def body_of(req: Request) -> dict:
    from ..main import body_of as _b
    return await _b(req)


@router.get("")
async def list_jobs():
    return [jobs.public(j) for j in await db.list_jobs()]


@router.get("/{job_id}")
async def get_job(job_id: str):
    v = await _view(job_id)
    return v if v else JSONResponse({"error": "not found"}, status_code=404)


@router.post("")
async def create_job(req: Request):
    body = await body_of(req)
    kind = body.get("kind", "client")
    if kind not in ("client", "own"):
        return JSONResponse({"error": 'kind must be "client" or "own"'}, status_code=400)
    if kind == "own":
        return JSONResponse({"error": "the own-product validation path needs the web evidence tools, which are not connected yet"}, status_code=400)
    title = str(body.get("title") or "").strip()
    if not title:
        return JSONResponse({"error": "title is required"}, status_code=400)
    tier = body.get("requestedTier", 0)
    if tier not in (0, 1, 2):
        return JSONResponse({"error": "requestedTier must be 0, 1 or 2"}, status_code=400)
    brief = {k: str(body.get(k) or "").strip()[:8000] for k in ("title", "description", "client", "deposit_ref", "acceptance")}
    brief["title"] = title
    job = jobs.new_job(kind, title, brief, requested_tier=tier)
    await db.save_job(job)
    cfgd = {"job_id": job["id"], "kind": kind, "brief": brief, "requested_tier": tier, "loops": {}, "feedback": "", "route": ""}
    _spawn(_drive(job["id"], cfgd))
    return jobs.public(job)


@router.post("/{job_id}/gates/{stage}")
async def decide_gate(job_id: str, stage: str, req: Request):
    """The owner's PASS/FAIL on the stage the job is waiting at."""
    body = await body_of(req)
    verdict = str(body.get("verdict", "")).upper()
    if verdict not in ("PASS", "FAIL"):
        return JSONResponse({"error": 'verdict must be "PASS" or "FAIL"'}, status_code=400)
    job = await db.get_job(job_id)
    if not job:
        return JSONResponse({"error": "not found"}, status_code=404)
    pending = next((p for p in job.get("pending", []) if p["stage"] == stage and exp.OWNER in p["roles"]), None)
    if job.get("status") != "waiting" or not pending:
        return JSONResponse({"error": f"the job is not waiting for the owner at {stage}"}, status_code=409)
    note = str(body.get("note") or "")[:1000]
    if not await db.record_approval(job_id, stage, exp.OWNER, verdict, note, [], exp.OWNER):
        return JSONResponse({"error": "the owner already decided this stage"}, status_code=409)
    if verdict == "PASS" and stage == "exposure" and int(job.get("requestedTier", 0)) == 1:
        await db.bump_counter("tier1_owner_clicks")
    await jobs.event(job_id, f"owner {verdict} on {stage}")
    _spawn(_drive(job_id, Command(resume={"owner": verdict})))
    return {"ok": True}


@router.post("/{job_id}/spawn")
async def spawn_subagent(job_id: str, req: Request):
    """A lead calls a bench role of its own department for a draft or a finding (information only)."""
    from . import spawn as sp
    body = await body_of(req)
    job = await db.get_job(job_id)
    if not job:
        return JSONResponse({"error": "not found"}, status_code=404)
    if job["status"] in jobs.TERMINAL:
        return JSONResponse({"error": "the job is finished"}, status_code=409)
    try:
        return await sp.spawn(str(body.get("lead") or ""), str(body.get("bench") or ""), str(body.get("task") or ""),
                              job_id=job_id, stage=str(body.get("stage") or job.get("stage") or ""))
    except sp.SpawnRefused as e:
        return JSONResponse({"error": str(e)}, status_code=403)


@router.post("/{job_id}/consult")
async def consult_lead(job_id: str, req: Request):
    """One department lead asks another a read-only question (information, never a verdict)."""
    from . import spawn as sp
    body = await body_of(req)
    job = await db.get_job(job_id)
    if not job:
        return JSONResponse({"error": "not found"}, status_code=404)
    if job["status"] in jobs.TERMINAL:
        return JSONResponse({"error": "the job is finished"}, status_code=409)
    try:
        return await sp.consult(str(body.get("from") or ""), str(body.get("to") or ""), str(body.get("question") or ""),
                                job_id=job_id, stage=str(body.get("stage") or job.get("stage") or ""))
    except sp.SpawnRefused as e:
        return JSONResponse({"error": str(e)}, status_code=403)


@router.post("/{job_id}/retry")
async def retry_parked(job_id: str, req: Request):
    body = await body_of(req)
    job = await db.get_job(job_id)
    if not job:
        return JSONResponse({"error": "not found"}, status_code=404)
    if job.get("status") != "parked":
        return JSONResponse({"error": "the job is not parked"}, status_code=409)
    _spawn(_drive(job_id, Command(resume={"action": "retry", "note": str(body.get("note") or "")[:1000]})))
    return {"ok": True}


@router.post("/{job_id}/kill")
async def kill_job(job_id: str):
    """Kill switch: stop the job, take the preview down, release the graph."""
    from .ports import get_deps
    job = await db.get_job(job_id)
    if not job:
        return JSONResponse({"error": "not found"}, status_code=404)
    if job["status"] in jobs.TERMINAL:
        return {"ok": True, "status": job["status"]}
    await jobs.touch(job_id, status="killed", pending=[])
    prev = job.get("preview")
    if prev and prev.get("app_id"):
        try:
            await get_deps().deployer.stop(job, prev)
        except Exception:
            log.exception("could not stop the preview of %s", job_id)
    _spawn(_drive(job_id, Command(resume={"action": "kill"})))
    await jobs.event(job_id, "killed by the owner")
    return {"ok": True, "status": "killed"}
