#!/usr/bin/env python3
"""Behaviour checklist for the go-live slice (only exec + engineering act as agents).

    BASE_URL=http://127.0.0.1:4520 [AO_API_TOKEN=...] python3 scripts/verify_slice.py [--scripted] [--with-restart]

Drives the real HTTP API only. Every line prints PASS / FAIL / SKIP with its evidence; the exit code is 1
on any FAIL. `--scripted` marks the lines that only mean something against real models as SKIP-able
(it is for proving this script against tests/ui_server.py). Writes data/verify-report.json.
"""
from __future__ import annotations

import json
import os
import subprocess
import sys
import time
from pathlib import Path

import httpx

ROOT = Path(__file__).resolve().parent.parent
BASE = os.environ.get("BASE_URL", "http://127.0.0.1:4520").rstrip("/")
SCRIPTED = "--scripted" in sys.argv
WITH_RESTART = "--with-restart" in sys.argv
LIVE = {"exec", "engineering"}
OFFLINE_LEADS = {"comply", "qa", "lexi", "alead", "elead", "mlead"}
OFFLINE_SEATS = {"piper", "cmail", "recon", "kmail", "vmail", "dash", "newt", "report", "imail", "riley", "gfx"}
BRIEF = {"title": "Bakery ordering site", "client": "Acme Bakery", "deposit_ref": "INV-001 paid",
         "description": "A small ordering site for a bakery: a menu page and an order form that emails the bakery.",
         "acceptance": "A customer can pick items from the menu and submit an order; the bakery receives it."}

headers = {"X-AO-Client": "office"}
if os.environ.get("AO_API_TOKEN"):
    headers["X-AO-Token"] = os.environ["AO_API_TOKEN"]
c = httpx.Client(base_url=BASE, headers=headers, timeout=60)
results: list[dict] = []


def check(name: str, ok: bool, detail: str = "", skip: bool = False) -> bool:
    status = "SKIP" if skip else ("PASS" if ok else "FAIL")
    results.append({"check": name, "status": status, "detail": detail})
    print(f"{status:5} {name}" + (f"  — {detail}" if detail else ""))
    return ok or skip


def get_job(jid):
    return c.get(f"/api/jobs/{jid}").json()


def wait_for(jid, pred, timeout=240.0):
    end = time.time() + timeout
    j = get_job(jid)
    while time.time() < end:
        j = get_job(jid)
        if pred(j):
            return j
        time.sleep(0.5)
    return j


def drive_as_owner(jid, stop=lambda j: False, timeout=600.0):
    """Click PASS only where the owner is pending; return the job when it ends or `stop(job)` is true."""
    end = time.time() + timeout
    clicked: list[str] = []
    while time.time() < end:
        j = get_job(jid)
        if j["status"] in ("done", "killed", "failed", "parked") or stop(j):
            return j, clicked
        if j["status"] == "waiting" and j.get("pending"):
            p = j["pending"][0]
            if p["roles"] == ["owner"] or "owner" in p["roles"] and not [r for r in p["roles"] if r != "owner"]:
                r = c.post(f"/api/jobs/{jid}/gates/{p['stage']}", json={"verdict": "PASS", "note": "verify_slice"})
                if r.status_code == 200:
                    clicked.append(p["stage"])
                time.sleep(0.4)
                continue
        time.sleep(0.5)
    return get_job(jid), clicked


def main() -> int:
    # 1. health
    h = c.get("/api/health").json()
    p = h.get("pipeline", {})
    check("health: the API answers", c.get("/api/health").status_code == 200)
    check("health: only exec and engineering are live", sorted(p.get("liveDepartments", [])) == sorted(LIVE), str(p.get("liveDepartments")))
    check("health: exposure is locked", p.get("exposureAllowed") is False)
    agents = h.get("agents", [])
    check("health: 27 seats in 8 departments", len(agents) == 27 and len({a.get("department") or a.get("dept") for a in agents}) == 8, f"{len(agents)} seats")

    # 2. tier 1 refused while security is offline
    r = c.post("/api/jobs", json={**BRIEF, "requestedTier": 1})
    check("gate: a gated (Tier 1) preview is refused while security is offline", r.status_code == 400, r.text[:120])

    # 3. the bakery job
    r = c.post("/api/jobs", json={**BRIEF, "requestedTier": 0})
    check("job: the bakery job is accepted", r.status_code == 200, r.text[:120])
    if r.status_code != 200:
        return finish()
    jid = r.json()["id"]
    wait_for(jid, lambda j: j["status"] == "waiting")
    # a lead cannot be recorded through HTTP: a gate for a stage that is not the pending one is refused
    bad = c.post(f"/api/jobs/{jid}/gates/handoff", json={"verdict": "PASS"})
    check("gate: a decision for a stage the job is not waiting at is refused", bad.status_code == 409, str(bad.status_code))

    job, clicked = drive_as_owner(jid, timeout=900)
    check("job: reaches done", job["status"] == "done", f'{job["status"]} {job.get("parkReason") or ""}')
    check("job: the owner was asked only for verify, security, preview and handoff",
          clicked == ["verify", "security", "preview", "handoff"] or sorted(set(clicked)) == ["handoff", "preview", "security", "verify"], str(clicked))

    appr: dict[str, set] = {}
    for a in job.get("approvals", []):
        appr.setdefault(a["stage"], set()).add(a["role"])
    expect = {"intake": None, "verify": {"olead", "owner"}, "scope": {"dlead"}, "build": {"dlead"},
              "security": {"owner"}, "preview": {"owner"}, "handoff": {"owner"}}
    for stage, want in expect.items():
        if want is None:
            continue
        check(f"approvals: {stage} is approved by {sorted(want)}", appr.get(stage) == want, str(sorted(appr.get(stage, []))))
    given = {r for rs in appr.values() for r in rs}
    check("approvals: no offline lead approved anything", not (given & OFFLINE_LEADS), str(sorted(given & OFFLINE_LEADS)))
    ev = job.get("evidence", [])
    ids = {e["id"] for e in ev}
    leads_pass = [a for a in job.get("approvals", []) if a["role"] != "owner" and a["verdict"] == "PASS"]
    check("approvals: every lead PASS cites evidence that exists", bool(leads_pass) and all(a.get("evidence") and set(a["evidence"]) <= ids for a in leads_pass),
          f"{len(leads_pass)} lead passes")

    # 4. evidence attribution
    seats = {e["stage"]: set() for e in ev}
    for e in ev:
        s = (e.get("body") or {}).get("seat")
        if e["kind"] == "finding" and s:
            seats[e["stage"]].add(s)
    check("evidence: verify findings come from scout, ilm, enzo", seats.get("verify", set()) == {"scout", "ilm", "enzo"}, str(seats.get("verify")))
    check("evidence: scope findings come from pco", seats.get("scope", set()) == {"pco"}, str(seats.get("scope")))
    allseats = {s for v in seats.values() for s in v} | {(e.get("body") or {}).get("seat") for e in ev if (e.get("body") or {}).get("seat")}
    check("evidence: no offline department's seat contributed", not (allseats & OFFLINE_SEATS), str(sorted(allseats & OFFLINE_SEATS)))
    sec = [e for e in ev if e["stage"] == "security" and e["kind"] == "check"]
    check("evidence: security checks ran and are not credited to an offline seat", bool(sec) and all((e["body"].get("seat") or "") == "" for e in sec), f"{len(sec)} checks")
    check("evidence: the build produced a patch", any(e["stage"] == "build" and e["kind"] == "patch" and e["ok"] for e in ev))

    # 5. sub-agents and consults
    j2 = c.post("/api/jobs", json={**BRIEF, "title": "Bakery spawn test", "requestedTier": 0}).json()["id"]
    wait_for(j2, lambda j: j["status"] in ("waiting", "running"))
    r = c.post(f"/api/jobs/{j2}/spawn", json={"lead": "comply", "bench": "sec-container", "task": "x", "stage": "security"})
    check("bench: an offline lead cannot spawn", r.status_code == 403 and "not live" in r.text, f"{r.status_code} {r.text[:80]}")
    r = c.post(f"/api/jobs/{j2}/spawn", json={"lead": "dlead", "bench": "eng-api-designer", "task": "Name the main API endpoints for an ordering site.", "stage": "scope"})
    check("bench: a live lead can spawn from its own bench", r.status_code == 200 and r.json().get("ok"), f"{r.status_code} {r.text[:80]}", skip=SCRIPTED and r.status_code != 200)
    r = c.post(f"/api/jobs/{j2}/consult", json={"from": "olead", "to": "lexi", "question": "x", "stage": "verify"})
    check("consult: asking an offline department's lead is refused", r.status_code == 403, str(r.status_code))
    r = c.post(f"/api/jobs/{j2}/consult", json={"from": "olead", "to": "dlead", "question": "How long would this take to build?", "stage": "verify"})
    check("consult: exec lead can ask the engineering lead", r.status_code == 200 and r.json().get("ok"), f"{r.status_code}", skip=SCRIPTED and r.status_code != 200)

    # 6. kill
    r = c.post(f"/api/jobs/{j2}/kill")
    j2v = wait_for(j2, lambda j: j["status"] == "killed", 30)
    check("kill: a running job can be killed", r.status_code == 200 and j2v["status"] == "killed", j2v["status"])

    # 7. cost metering
    check("costs: the job carries a cost record", set(job.get("costs", {})) >= {"tokens", "usd"}, str(job.get("costs")))
    check("costs: the job stayed under its cap", float(job.get("costs", {}).get("usd", 0)) <= 1.0, str(job.get("costs")))
    check("costs: /api/usage answers", c.get("/api/usage").status_code == 200)

    # 8. restart / resume
    if WITH_RESTART:
        j3 = c.post("/api/jobs", json={**BRIEF, "title": "Bakery restart test", "requestedTier": 0}).json()["id"]
        wait_for(j3, lambda j: j["status"] == "waiting" and j["pending"] and j["pending"][0]["stage"] == "verify")
        before = len([e for e in get_job(j3)["evidence"] if e["stage"] == "verify"])
        subprocess.run(os.environ.get("AO_RESTART_CMD") or str(ROOT / "scripts" / "restart_api.sh"), shell=True, check=True)
        end = time.time() + 90
        while time.time() < end:
            try:
                if c.get("/api/health").status_code == 200:
                    break
            except httpx.HTTPError:
                pass
            time.sleep(1)
        waiting = get_job(j3)
        check("restart: the job is still waiting at verify after the API restarted",
              waiting["status"] == "waiting" and waiting["pending"][0]["stage"] == "verify", waiting["status"])
        r = c.post(f"/api/jobs/{j3}/gates/verify", json={"verdict": "PASS"})
        j3v, _ = drive_as_owner(j3, stop=lambda j: j["stage"] in ("scope", "build", "security"), timeout=300)
        after = [e for e in j3v["evidence"] if e["stage"] == "verify"]
        check("restart: resumed exactly once (no duplicated verify evidence)", r.status_code == 200 and len(after) == before, f"{before} -> {len(after)}")
        c.post(f"/api/jobs/{j3}/kill")
    else:
        check("restart: kill the API while a job waits, then approve", False, "run with --with-restart on the laptop", skip=True)
    return finish()


def finish() -> int:
    out = ROOT / "data"
    out.mkdir(exist_ok=True)
    (out / "verify-report.json").write_text(json.dumps({"at": time.time(), "base": BASE, "scripted": SCRIPTED, "results": results}, indent=1))
    bad = [r for r in results if r["status"] == "FAIL"]
    n = {s: sum(1 for r in results if r["status"] == s) for s in ("PASS", "FAIL", "SKIP")}
    print(f"\n{n['PASS']} passed, {n['FAIL']} failed, {n['SKIP']} skipped  ->  data/verify-report.json")
    if SCRIPTED:
        print("SCRIPTED run: this proves the wiring and the slice rules, not model quality, the real worker or Docker.")
    return 1 if bad else 0


if __name__ == "__main__":
    sys.exit(main())
