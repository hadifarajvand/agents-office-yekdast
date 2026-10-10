#!/usr/bin/env python3
"""Behaviour checklist for the go-live slice (exec, engineering, security and devops act as agents).

    BASE_URL=http://127.0.0.1:4597 [AO_API_TOKEN=...] python3 scripts/verify_slice.py --allow-test-database [--scripted] [--with-restart]

THIS SCRIPT CREATES AND ADVANCES REAL JOBS (it submits briefs, clicks the owner's gates and kills what is left).
It therefore refuses to run unless all of these hold, and it checks them before it creates anything:
  - `--allow-test-database` is given;
  - BASE_URL is a loopback address;
  - the server itself reports (GET /api/health -> database.name) a database whose name ends in _ui, _test or _verify;
  - with `--with-restart`, AO_RESTART_CMD names the command that restarts THIS stack (scripts/restart_api.sh restarts
    the live API, so it is never the default).
Point it at `python -m tests.ui_server <port>` (see backend/tests/ui_server.py) on a throwaway database, not at the office.

Drives the real HTTP API only. Every line prints PASS / FAIL / SKIP with its evidence; the exit code is 1 on any FAIL
and 2 when it refused to start. `--scripted` marks the lines that only mean something against real models as SKIP-able
(it is for proving this script against tests/ui_server.py). Writes data/verify-report.json.

What it expects is derived from /api/health (live departments, stage leads, the roster), not typed in, except the few
pinned numbers below; backend/tests/test_verify_slice_guard.py fails when a pinned number drifts from the app.
"""
from __future__ import annotations

import json
import os
import subprocess
import sys
import time
from pathlib import Path
from urllib.parse import urlsplit

import httpx

ROOT = Path(__file__).resolve().parent.parent
FLAG = "--allow-test-database"
TEST_DB_SUFFIXES = ("_ui", "_test", "_verify")
DEFAULT_BASE = "http://127.0.0.1:4520"
# Build-lane stages whose lead is not enough: the owner must also click (pipeline.owner_gates minus the validate
# lane's "research").
OWNER_GATES = {"verify", "handoff"}
SEATS, DEPARTMENTS = 17, 8  # the seeded roster (backend/app/seed/roster_seed.json)
CHECKLIST_ITEMS = 5         # connectors/promote.py checklist()
BRIEF = {"title": "Bakery ordering site", "client": "Acme Bakery", "deposit_ref": "INV-001: 50% deposit (USD 600) received 2026-10-01, signed contract C-17",
         "price": "USD 1,200 fixed price; 50% deposit paid, 50% on delivery", "audience": "local customers ordering pickup, about 30 orders a week",
         "description": "A small ordering site for a bakery: a menu page and an order form that emails the bakery.",
         "acceptance": "A customer can pick items from the menu and submit an order; the bakery receives it."}

BASE = DEFAULT_BASE
SCRIPTED = False
WITH_RESTART = False
DB_NAME = ""
c: httpx.Client | None = None  # built by connect(), only after the guard has passed
created: list[str] = []  # every job this run submits; finish() kills the ones still open so they do not pile up in the owner's inbox
results: list[dict] = []


# ---------- the guard ----------
def is_loopback(base: str) -> bool:
    try:
        u = urlsplit(base)
        return u.scheme in ("http", "https") and u.hostname in ("127.0.0.1", "localhost", "::1")
    except ValueError:
        return False


def preflight(base: str, allowed: bool, with_restart: bool = False, restart_cmd: str = "") -> str | None:
    """Why this run must not start, from what is known before any HTTP call; None when it may go on."""
    if not allowed:
        return (f"refusing to run: this script creates and advances real jobs. Pass {FLAG} only against a throwaway "
                "stack (python -m tests.ui_server on an *_ui database), never the live office.")
    if not is_loopback(base):
        return f"refusing to run: BASE_URL {base!r} is not a loopback address (http://127.0.0.1:<port> or http://localhost:<port>)"
    if with_restart and not restart_cmd:
        return ("refusing --with-restart: set AO_RESTART_CMD to the command that restarts THIS stack. "
                "scripts/restart_api.sh restarts the live API, so it is not used by default.")
    return None


def check_database(health) -> str | None:
    """Why this server must not be driven, from what it says about itself; None when it names a throwaway database."""
    info = health.get("database") if isinstance(health, dict) else None
    name = info.get("name") if isinstance(info, dict) else None
    if not isinstance(name, str) or not name:
        return ("refusing to run: the server does not report which database it uses (restart it with the current code), "
                "so it cannot be shown to be a test database")
    if not name.endswith(TEST_DB_SUFFIXES):
        return (f"refusing to run: the server uses database {name!r}, which is not a throwaway database "
                f"(its name must end in {', '.join(TEST_DB_SUFFIXES)})")
    return None


def fetch_health(base: str) -> dict:
    r = httpx.get(base + "/api/health", timeout=15)  # token-exempt, read-only
    r.raise_for_status()
    return r.json()


def connect(base: str) -> None:
    """Build the HTTP client. Called once, after the guard; this is the first place that is allowed to write."""
    global c
    headers = {"X-AO-Client": "office"}
    token = os.environ.get("AO_API_TOKEN", "")
    if not token:  # the server makes its own token per boot and hands it to the page, like the browser gets it
        import re
        import urllib.request
        m = re.search(r'name="ao-token" content="([^"]+)"', urllib.request.urlopen(base + "/", timeout=15).read().decode())
        token = m.group(1) if m else ""
    if token:
        headers["X-AO-Token"] = token
    c = httpx.Client(base_url=base, headers=headers, timeout=60)
    c.event_hooks["response"] = [_track]


# ---------- expectations derived from /api/health ----------
def expected_roles(stage: dict, live: set) -> set:
    """Roles whose PASS a Tier 0 job records at `stage` (mirrors pipeline/exposure.stage_roles)."""
    if stage["name"] == "exposure":
        return set()  # nothing to approve below Tier 1
    if stage["dept"] not in live:
        return {"owner"}  # an offline department's stage waits for the owner
    return {stage["lead"]} | ({"owner"} if stage["name"] in OWNER_GATES else set())


def expected_owner_clicks(pipeline: dict) -> list[str]:
    """Build-lane stages where the owner has to click (after the lead has passed, if there is one), in lane order."""
    live = set(pipeline.get("liveDepartments", []))
    by_name = {s["name"]: s for s in pipeline.get("stages", [])}
    return [n for n in pipeline["lanes"]["build"]["stages"] if "owner" in expected_roles(by_name[n], live)]


def offline_ids(agents: list, live: set) -> tuple[set, set]:
    """(lead ids, seat ids) of the departments that are not live."""
    off = [a for a in agents if a.get("department") not in live]
    return {a["id"] for a in off if a.get("lead")}, {a["id"] for a in off if not a.get("lead")}


# ---------- helpers ----------
def _track(resp):
    if resp.request.method == "POST" and resp.request.url.path == "/api/jobs" and resp.status_code == 200:
        try:
            created.append(resp.json()["id"])
        except Exception:
            pass


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


# ---------- the checks ----------
def run() -> int:
    # 1. health
    h = c.get("/api/health").json()
    p = h.get("pipeline", {})
    live = set(p.get("liveDepartments", []))
    stages = {s["name"]: s for s in p.get("stages", [])}
    build_lane = p.get("lanes", {}).get("build", {}).get("stages", [])
    agents = h.get("agents", [])
    departments = {a.get("department") for a in agents}
    off_leads, off_seats = offline_ids(agents, live)
    check("health: the API answers", c.get("/api/health").status_code == 200)
    check("health: the live departments are real departments and include exec", bool(live) and live <= departments and "exec" in live, str(sorted(live)))
    keys = (p.get("exposure") or {}).get("keys") or {}
    check("health: exposure is open exactly when Strategy and Security are live and the keys are set",
          p.get("exposureAllowed") is ({"secdata", "exec"} <= live and bool(keys)), f'allowed={p.get("exposureAllowed")} live={sorted(live)}')
    check(f"health: {SEATS} seats in {DEPARTMENTS} departments", len(agents) == SEATS and len(departments) == DEPARTMENTS, f"{len(agents)} seats, {len(departments)} departments")

    # 2. tier 1 while exposure is closed
    if p.get("exposureAllowed"):
        check("gate: a gated (Tier 1) preview is refused while security is offline", False,
              "exposure is open here, so Tier 1 is accepted; not tried, to avoid creating a gated job", skip=True)
    else:
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
    want_clicks = expected_owner_clicks(p)
    check("job: reaches done", job["status"] == "done", f'{job["status"]} {job.get("parkReason") or ""}')
    check(f"job: the owner was asked only for {', '.join(want_clicks)}", clicked == want_clicks, str(clicked))

    appr: dict[str, set] = {}
    for a in job.get("approvals", []):
        appr.setdefault(a["stage"], set()).add(a["role"])
    for stage in build_lane:
        want = expected_roles(stages[stage], live)
        if stage == "intake" or not want:
            continue
        check(f"approvals: {stage} is approved by {sorted(want)}", appr.get(stage) == want, str(sorted(appr.get(stage, []))))
    given = {r for rs in appr.values() for r in rs}
    check("approvals: no offline lead approved anything", not (given & off_leads), str(sorted(given & off_leads)))
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
    if p.get("seatsEnabled"):
        check("evidence: verify findings come from scout, ilm, enzo", seats.get("verify", set()) == {"scout", "ilm", "enzo"}, str(seats.get("verify")))
        check("evidence: scope findings come from pco", seats.get("scope", set()) == {"pco"}, str(seats.get("scope")))
    else:
        check("evidence: seats are off, so no seat findings were made", not any(seats.values()), str(seats))
    allseats = {s for v in seats.values() for s in v} | {(e.get("body") or {}).get("seat") for e in ev if (e.get("body") or {}).get("seat")}
    check("evidence: no offline department's seat contributed", not (allseats & off_seats), str(sorted(allseats & off_seats)))
    sec = [e for e in ev if e["stage"] == "security" and e["kind"] == "check"]
    check("evidence: security checks ran and are not credited to an offline seat", bool(sec) and all((e["body"].get("seat") or "") == "" for e in sec), f"{len(sec)} checks")
    check("evidence: the build produced a patch", any(e["stage"] == "build" and e["kind"] == "patch" and e["ok"] for e in ev))

    # 4a. production: the owner's Promote button
    pr = c.get(f"/api/jobs/{jid}/promote")
    st = pr.json() if pr.status_code == 200 else {}
    check("promote: the finished job has a computed production checklist", pr.status_code == 200 and len(st.get("checklist", [])) == CHECKLIST_ITEMS,
          "; ".join(f'{"ok" if ck["ok"] else "NO"} {ck["name"]}' for ck in st.get("checklist", [])))
    r = c.post(f"/api/jobs/{jid}/promote", json={"step": "deploy", "envConfirmed": True})
    check("promote: deploying before prepare is refused", r.status_code == 409, f"{r.status_code}")
    if SCRIPTED and st.get("ready"):
        r = c.post(f"/api/jobs/{jid}/promote", json={"step": "prepare", "domain": "orders.example.com"})
        check("promote: prepare makes the repo and the production app, not deployed", r.status_code == 200 and r.json()["production"]["state"] == "prepared", r.text[:120])
        r = c.post(f"/api/jobs/{jid}/promote", json={"step": "deploy"})
        check("promote: deploy needs the owner to confirm the variables", r.status_code == 400, f"{r.status_code}")
        r = c.post(f"/api/jobs/{jid}/promote", json={"step": "deploy", "envConfirmed": True})
        check("promote: deploy probes /healthz and reports live", r.status_code == 200 and r.json()["production"]["state"] == "live", r.text[:120])
    else:
        check("promote: prepare/deploy", False, "real GitHub + Dokploy: do it by hand from the Jobs screen (runbook S6)", skip=True)

    # 4b. validate lane: own idea -> web research -> computed verdict -> owner
    r = c.post("/api/jobs", json={"kind": "own", "title": "Bakery order inbox",
                                  "description": "One list of phone, Instagram and walk-in orders for small bakeries, with pickup times."})
    check("validate: an own idea is accepted into the validate lane", r.status_code == 200 and r.json().get("lane") == "validate", r.text[:120])
    if r.status_code == 200:
        vid = r.json()["id"]
        vj, vclicked = drive_as_owner(vid, timeout=300)
        check("validate: the job runs intake -> research and the owner closes it",
              vj["status"] == "done" and [s["name"] for s in vj["stages"]] == ["intake", "research"] and vclicked == ["research"],
              f'{vj["status"]} {vclicked}')
        memo = next((e for e in vj.get("evidence", []) if e["stage"] == "research" and e["kind"] == "memo"), None)
        body = (memo or {}).get("body") or {}
        check("validate: the memo carries a computed verdict and gate table",
              body.get("verdict") in ("GO", "TEST", "NO-GO") and set(body.get("gates", {})) == {"D1", "D2", "A"}, str(body.get("verdict")))
        pages = set((body.get("run_log") or {}).get("pages") or [])
        check("validate: every kept claim cites a page that was actually fetched",
              all(cl.get("url") in pages for cl in body.get("claims", [])), f'{len(body.get("claims", []))} claims, {len(pages)} pages')
        if not (body.get("run_log") or {}).get("search_available"):
            check("validate: without a search tool the verdict cannot be GO", body.get("verdict") != "GO", str(body.get("verdict")))
        r = c.post("/api/jobs", json={**BRIEF, "kind": "own", "lane": "build", "fromJob": vid, "title": "Bakery order inbox MVP"})
        check("validate: a finished validate job can seed an own-idea build job", r.status_code == 200, r.text[:120])
        if r.status_code == 200:
            c.post(f'/api/jobs/{r.json()["id"]}/kill')

    # 4c. the owner's inbox
    ib = c.get("/api/inbox")
    kinds = [i.get("kind") for i in (ib.json() if ib.status_code == 200 else [])]
    check("inbox: one list of what waits for the owner answers", ib.status_code == 200 and all(k in ("gate", "parked", "production", "promote", "memo") for k in kinds), str(kinds))

    # 5. sub-agents and consults
    j2 = c.post("/api/jobs", json={**BRIEF, "title": "Bakery spawn test", "requestedTier": 0}).json()["id"]
    wait_for(j2, lambda j: j["status"] in ("waiting", "running"))
    offline_lead = sorted(off_leads)[0] if off_leads else ""
    if offline_lead:
        r = c.post(f"/api/jobs/{j2}/spawn", json={"lead": offline_lead, "bench": "x", "task": "x", "stage": "security"})
        check("bench: an offline lead cannot spawn", r.status_code == 403 and "not live" in r.text, f"{offline_lead}: {r.status_code} {r.text[:80]}")
    else:
        check("bench: an offline lead cannot spawn", False, "every department is live", skip=True)
    r = c.post(f"/api/jobs/{j2}/spawn", json={"lead": "exec-vp-engineering", "bench": "eng-api-designer", "task": "Name the main API endpoints for an ordering site.", "stage": "scope"})
    check("bench: a live lead can spawn from its own bench", r.status_code == 200 and r.json().get("ok"), f"{r.status_code} {r.text[:80]}", skip=SCRIPTED and r.status_code != 200)
    if offline_lead:
        r = c.post(f"/api/jobs/{j2}/consult", json={"from": "exec-ceo-strategist", "to": offline_lead, "question": "x", "stage": "verify"})
        check("consult: asking an offline department's lead is refused", r.status_code == 403, f"{offline_lead}: {r.status_code}")
    else:
        check("consult: asking an offline department's lead is refused", False, "every department is live", skip=True)
    r = c.post(f"/api/jobs/{j2}/consult", json={"from": "exec-ceo-strategist", "to": "exec-vp-engineering", "question": "How long would this take to build?", "stage": "verify"})
    check("consult: exec lead can ask the engineering lead", r.status_code == 200 and r.json().get("ok"), f"{r.status_code}", skip=SCRIPTED and r.status_code != 200)

    # 6. kill
    r = c.post(f"/api/jobs/{j2}/kill")
    j2v = wait_for(j2, lambda j: j["status"] == "killed", 30)
    check("kill: a running job can be killed", r.status_code == 200 and j2v["status"] == "killed", j2v["status"])

    # 7. cost metering
    check("costs: the job carries a cost record", set(job.get("costs", {})) >= {"tokens", "usd"}, str(job.get("costs")))
    cap = float(((p.get("budget") or {}).get("build") or {}).get("usd", 5.0))
    check("costs: the job stayed under its lane cap", float(job.get("costs", {}).get("usd", 0)) <= cap, f'{job.get("costs")} cap ${cap}')
    check("costs: /api/usage answers", c.get("/api/usage").status_code == 200)

    # 8. restart / resume (AO_RESTART_CMD is required by the guard: it must restart this stack, not the live API)
    if WITH_RESTART:
        j3 = c.post("/api/jobs", json={**BRIEF, "title": "Bakery restart test", "requestedTier": 0}).json()["id"]
        wait_for(j3, lambda j: j["status"] == "waiting" and j["pending"] and j["pending"][0]["stage"] == "verify")
        before = len([e for e in get_job(j3)["evidence"] if e["stage"] == "verify"])
        subprocess.run(os.environ["AO_RESTART_CMD"], shell=True, check=True)
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
        check("restart: kill the API while a job waits, then approve", False, "run with --with-restart and AO_RESTART_CMD on the laptop", skip=True)
    return finish()


def cleanup_jobs() -> None:
    for jid in created:
        try:
            if get_job(jid).get("status") not in ("killed", "done"):
                c.post(f"/api/jobs/{jid}/kill")
        except Exception:
            pass


def finish() -> int:
    cleanup_jobs()
    out = ROOT / "data"
    out.mkdir(exist_ok=True)
    (out / "verify-report.json").write_text(json.dumps({"at": time.time(), "base": BASE, "database": DB_NAME, "scripted": SCRIPTED, "results": results}, indent=1))
    bad = [r for r in results if r["status"] == "FAIL"]
    n = {s: sum(1 for r in results if r["status"] == s) for s in ("PASS", "FAIL", "SKIP")}
    print(f"\n{n['PASS']} passed, {n['FAIL']} failed, {n['SKIP']} skipped  ->  data/verify-report.json")
    if SCRIPTED:
        print("SCRIPTED run: this proves the wiring and the slice rules, not model quality, the real worker or Docker.")
    return 1 if bad else 0


def refuse(why: str) -> int:
    print(why, file=sys.stderr)
    return 2


def main(argv: list[str] | None = None) -> int:
    global BASE, SCRIPTED, WITH_RESTART, DB_NAME
    argv = sys.argv[1:] if argv is None else argv
    BASE = os.environ.get("BASE_URL", DEFAULT_BASE).rstrip("/")
    SCRIPTED, WITH_RESTART = "--scripted" in argv, "--with-restart" in argv
    why = preflight(BASE, FLAG in argv, WITH_RESTART, os.environ.get("AO_RESTART_CMD", ""))
    if why:
        return refuse(why)
    try:
        health = fetch_health(BASE)
    except Exception as e:
        return refuse(f"refusing to run: cannot read {BASE}/api/health ({type(e).__name__}), so the database cannot be checked")
    why = check_database(health)
    if why:
        return refuse(why)
    DB_NAME = health["database"]["name"]
    print(f"target {BASE}, database {DB_NAME!r}")
    connect(BASE)
    return run()


if __name__ == "__main__":
    sys.exit(main())
