"""Jobs API: create jobs, read them, record the owner's decisions, kill.

Only the owner acts through HTTP. Lead approvals are written by the graph itself
(leads.review -> db.record_approval); an HTTP request can never record a lead's PASS.
"""
from __future__ import annotations

import asyncio
import logging

from fastapi import APIRouter, Request
from fastapi.responses import JSONResponse, StreamingResponse
from langgraph.types import Command

from .. import db, jobqueue
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


async def dispatch(job_id: str, payload) -> None:
    """Hand a start/resume/kill to the worker queue, or run it in this process when the queue is off."""
    if jobqueue.enabled() and await jobqueue.enqueue(job_id, payload):
        return
    _spawn(_drive(job_id, payload))


async def _view(job_id: str) -> dict | None:
    job = await db.get_job(job_id)
    if job is None:
        return None
    return jobs.public(job, await db.list_approvals(job_id), await db.list_evidence(job_id))


async def body_of(req: Request) -> dict:
    from ..main import body_of as _b
    return await _b(req)


@router.get("")
async def list_jobs(archived: bool = False):
    # rows that are not complete job records (e.g. written by a test) are skipped, not fatal;
    # archived jobs are hidden from the list but their records stay (?archived=true shows them)
    return [jobs.public(j) for j in await db.list_jobs()
            if j.get("stages") and j.get("status") and (archived or not j.get("archived"))]


@router.get("/{job_id}/stream")
async def stream_job(job_id: str):
    """Server-sent events: the job's public view whenever it changes, until it reaches a final state.
    Reads Postgres, so it sees changes made by the API process and by the queue worker alike."""
    import json

    if await db.get_job(job_id) is None:
        return JSONResponse({"error": "not found"}, status_code=404)

    async def gen():
        last, idle = None, 0
        while True:
            v = await _view(job_id)
            if v is None:
                yield "event: gone\ndata: {}\n\n"
                return
            blob = json.dumps(v, sort_keys=True, default=str)
            if blob != last:
                last, idle = blob, 0
                yield f"data: {blob}\n\n"
            else:
                idle += 1
                if idle % 15 == 0:
                    yield ": keep-alive\n\n"
            if v.get("status") in jobs.TERMINAL:
                return
            await asyncio.sleep(1)

    return StreamingResponse(gen(), media_type="text/event-stream", headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"})


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
    lane = body.get("lane") or ("validate" if kind == "own" else "build")
    if lane not in jobs.LANES:
        return JSONResponse({"error": 'lane must be "validate" or "build"'}, status_code=400)
    if kind == "own" and lane == "build":
        src = await db.get_job(str(body.get("fromJob") or ""))
        if not src or src.get("lane") != "validate" or src.get("status") != "done":
            return JSONResponse({"error": "an own idea is built only from a finished validate job (fromJob)"}, status_code=400)
    title = str(body.get("title") or "").strip()
    if not title:
        return JSONResponse({"error": "title is required"}, status_code=400)
    tier = body.get("requestedTier", 0)
    if tier not in (0, 1, 2):
        return JSONResponse({"error": "requestedTier must be 0, 1 or 2"}, status_code=400)
    if tier > 0 and not exp.exposure_allowed(load_config()):
        return JSONResponse({"error": "gated and public previews need Strategy & Legal and Security & Privacy live; "
                                      "only private (Tier 0) previews exist until then"}, status_code=400)
    brief = {k: str(body.get(k) or "").strip()[:8000]
             for k in ("title", "description", "client", "deposit_ref", "acceptance", "audience", "price", "links", "fromJob")}
    brief["title"] = title
    job = jobs.new_job(kind, title, brief, requested_tier=tier, lane=lane)
    await db.save_job(job)
    if kind == "own" and lane == "build":  # the memo was acted on: it leaves the owner's inbox
        try:
            await jobs.touch(str(body["fromJob"]), followedBy=job["id"])
        except KeyError:
            pass
    cfgd = {"job_id": job["id"], "kind": kind, "lane": lane, "brief": brief, "requested_tier": tier, "loops": {}, "feedback": "", "route": ""}
    await dispatch(job["id"], cfgd)
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
    await dispatch(job_id, Command(resume={"owner": verdict}))
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
    snap = await compiled().aget_state(thread(job_id))
    if snap.interrupts:
        payload = Command(resume={"action": "retry", "note": str(body.get("note") or "")[:1000]})
    else:
        payload = None  # parked by a restart, not by the graph: continue from the last checkpoint
    await dispatch(job_id, payload)
    return {"ok": True}


async def park_interrupted() -> int:
    """On startup, a job still 'running' lost its driver in the restart (nothing re-drives it).
    Park it with a reason so the owner can press Retry; nothing restarts by itself."""
    n = 0
    for j in await db.list_jobs():
        if j.get("status") == "running" and j.get("id"):
            await jobs.touch(j["id"], status="parked", parkReason="interrupted by a restart — press Retry to continue from the last checkpoint")
            await jobs.event(j["id"], "interrupted by a restart; parked")
            n += 1
    return n


@router.post("/{job_id}/archive")
async def archive_job(job_id: str, req: Request):
    """Owner only: hide a finished, killed, failed or parked job from the list. Nothing is deleted."""
    await body_of(req)  # same owner-client check as every mutating call
    job = await db.get_job(job_id)
    if job is None:
        return JSONResponse({"error": "not found"}, status_code=404)
    if job.get("status") == "running":
        return JSONResponse({"error": "a running job cannot be archived; kill or park it first"}, status_code=409)
    await jobs.touch(job_id, archived=True)
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
    from ..sandbox import stop_job_container
    await asyncio.to_thread(stop_job_container, job_id)  # a killed job's agent must stop using the router
    prev = job.get("preview")
    if prev and prev.get("app_id"):
        try:
            await get_deps().deployer.stop(job, prev)
        except Exception:
            log.exception("could not stop the preview of %s", job_id)
    await dispatch(job_id, Command(resume={"action": "kill"}))
    await jobs.event(job_id, "killed by the owner")
    return {"ok": True, "status": "killed"}


# ---------- production: the owner's Promote button (never reachable from the graph or an agent) ----------

@router.get("/{job_id}/promote")
async def promote_status(job_id: str):
    from ..connectors.promote import checklist
    job = await db.get_job(job_id)
    if not job:
        return JSONResponse({"error": "not found"}, status_code=404)
    items = checklist(job, await db.list_evidence(job_id))
    return {"checklist": items, "ready": all(i["ok"] for i in items), "production": job.get("production")}


@router.post("/{job_id}/promote")
async def promote(job_id: str, req: Request):
    """step "prepare" {domain}: repo + production app, not deployed; step "deploy" {envConfirmed}: deploy + probe."""
    from ..connectors.promote import HOST, checklist, env_names
    from .ports import get_deps
    body = await body_of(req)
    job = await db.get_job(job_id)
    if not job:
        return JSONResponse({"error": "not found"}, status_code=404)
    items = checklist(job, await db.list_evidence(job_id))
    if not all(i["ok"] for i in items):
        return JSONResponse({"error": "not ready for production: " + "; ".join(i["name"] for i in items if not i["ok"])}, status_code=409)
    step, prod = str(body.get("step") or ""), dict(job.get("production") or {})
    promoter = get_deps().promoter
    if step == "prepare":
        domain = str(body.get("domain") or "").strip().lower()
        if not HOST.match(domain):
            return JSONResponse({"error": "give the production domain, e.g. app.example.com"}, status_code=400)
        if prod.get("state") in ("deploying", "live"):
            return JSONResponse({"error": "this job is already in production"}, status_code=409)
        bundle = ((job.get("patch") or {}).get("path")) or next(
            (e["body"].get("patch_path") for e in reversed(await db.list_evidence(job_id))
             if e["stage"] == "build" and e["kind"] == "patch" and e.get("ok")), "")
        if not bundle:
            return JSONResponse({"error": "the job has no approved build to promote"}, status_code=409)
        try:
            out = await promoter.prepare(job, bundle, domain)
        except Exception as e:
            log.exception("promote prepare failed for %s", job_id)
            return JSONResponse({"error": f"prepare failed: {str(e)[:200]}"}, status_code=502)
        prod = {**out, "state": "prepared", "domain": domain, "env": env_names(str(bundle).rsplit("/", 1)[0]),
                "preparedAt": db.now_ms()}
        await jobs.touch(job_id, production=prod)
        await jobs.event(job_id, f"owner prepared production at {domain}")
        return {"ok": True, "production": prod}
    if step == "deploy":
        if prod.get("state") not in ("prepared", "unhealthy"):
            return JSONResponse({"error": "prepare production first"}, status_code=409)
        if body.get("envConfirmed") is not True:
            return JSONResponse({"error": "confirm that the production variables are set in Dokploy"}, status_code=400)
        await jobs.touch(job_id, production={**prod, "state": "deploying"})
        try:
            res = await promoter.deploy(prod)
        except Exception as e:
            log.exception("promote deploy failed for %s", job_id)
            await jobs.touch(job_id, production={**prod, "state": "prepared"})
            return JSONResponse({"error": f"deploy failed: {str(e)[:200]}"}, status_code=502)
        prod = {**prod, "state": "live" if res.get("ok") else "unhealthy", "probe": res, "deployedAt": db.now_ms()}
        await jobs.touch(job_id, production=prod)
        await jobs.event(job_id, f'production {prod["state"]}: {prod["url"]} (healthz {res.get("status")})')
        return {"ok": bool(res.get("ok")), "production": prod}
    return JSONResponse({"error": 'step must be "prepare" or "deploy"'}, status_code=400)


# ---------- the owner's inbox: everything that waits for the CEO, newest first ----------

inbox_router = APIRouter(prefix="/api/inbox")


@inbox_router.get("")
async def inbox():
    """Gates waiting for the owner, parked jobs, finished builds ready to promote, production that
    did not come up healthy. One list, so the owner never has to walk the office to find work."""
    from ..connectors.promote import checklist
    items = []
    for j in await db.list_jobs():
        if not (j.get("stages") and j.get("status")):
            continue
        base = {"jobId": j["id"], "title": j.get("title", ""), "lane": j.get("lane", "build")}
        p = (j.get("pending") or [{}])[0]
        if j["status"] == "waiting" and p.get("needsOwner"):
            items.append({**base, "kind": "gate", "stage": p["stage"], "text": f'decide {p["stage"]}'})
        elif j["status"] == "parked":
            items.append({**base, "kind": "parked", "stage": j.get("stage"), "text": (j.get("parkReason") or "")[:200]})
        elif j["status"] == "done" and j.get("lane", "build") == "build":
            prod = j.get("production") or {}
            if prod.get("state") == "unhealthy":
                items.append({**base, "kind": "production", "text": "production did not answer /healthz"})
            elif prod.get("state") == "prepared":
                items.append({**base, "kind": "production", "text": "set the production variables, then deploy"})
            elif not prod and all(i["ok"] for i in checklist(j, await db.list_evidence(j["id"]))):
                items.append({**base, "kind": "promote", "text": "ready to promote to production"})
        elif j["status"] == "done" and j.get("lane") == "validate" and not j.get("followedBy"):
            items.append({**base, "kind": "memo", "text": "market memo ready: build a test or the MVP, or drop it"})
    order = {"gate": 0, "parked": 1, "production": 2, "promote": 3, "memo": 4}
    return sorted(items, key=lambda i: order[i["kind"]])
