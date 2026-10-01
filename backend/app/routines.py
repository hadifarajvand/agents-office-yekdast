"""Port of routines.mjs — routines: tasks the office does on its own clock.

A routine is a line in <brain>/Agents Office/routines.json. Run state lives separately
(originally data/routines.json; this backend keeps it in Postgres — see db.py) so the
brain file stays clean config. This release: routines are for Content, Finance and
Revenue only (the direct successors of the old Emails/Accounting/Sales pods).
"""
from __future__ import annotations

import json
import re
from pathlib import Path

from .when import describe, next_run, valid

ALLOWED = ["content", "fin", "revenue"]
NAMES = {"content": "Content", "fin": "Finance", "revenue": "Revenue", "exec": "Exec", "engineering": "Engineering", "frontend": "Frontend", "devops": "Devops", "secdata": "Secdata"}
LATE_AFTER = 90 * 1000  # ms


def file(brain_path: Path) -> Path:
    return brain_path / "Agents Office" / "routines.json"


def _slug(t: str) -> str:
    s = re.sub(r"[^a-z0-9]+", "-", str(t).lower())
    return s.strip("-")[:40]


def _read_json(p: Path, fallback):
    try:
        return json.loads(p.read_text())
    except Exception:
        return fallback


def refusal(dept: str) -> str:
    return f"Routines come to {NAMES.get(dept, dept)} in a later release. This release: Content, Finance and Revenue."


def validate(r: dict, agents: list, existing: list[dict] | None = None) -> dict:
    existing = existing or []
    problems: list[str] = []
    out: dict = {}
    a = next((x for x in agents if x.id == r.get("agent")), None)
    out["dept"] = r.get("dept") or (a.department if a else None)
    label = r.get("id") or r.get("title") or "routine"
    if out["dept"] not in ALLOWED:
        problems.append(f"{label}: {refusal(out['dept'])}")
    if not a:
        problems.append(f'{label}: no agent called "{r.get("agent")}"')
    elif a.department != out["dept"]:
        problems.append(f"{label}: {a.name} is in {NAMES.get(a.department, a.department)}, not {NAMES.get(out['dept'], out['dept'])}")
    out["agent"] = r.get("agent")
    out["text"] = str(r.get("text") or "").strip()
    if not out["text"]:
        problems.append(f'{r.get("id", "routine")}: no task text')
    out["title"] = str(r.get("title") or out["text"]).strip()[:90]
    out["id"] = str(r.get("id") or _slug(out["title"]) or "routine")
    if any(x["id"] == out["id"] for x in existing):
        problems.append(f'{out["id"]}: two routines share this id')
    out["when"] = r.get("when")
    if not valid(out["when"]):
        problems.append(f'{out["id"]}: the schedule is not complete ({json.dumps(r.get("when"))}) — see when.py')
    out["needsOk"] = r.get("needsOk") is not False
    out["paused"] = r.get("paused") is True
    if isinstance(r.get("plan"), list):
        out["plan"] = [str(x) for x in r["plan"][:4]]
    if r.get("model") not in (None, ""):
        m = str(r["model"]).lower().strip()
        if m in ("sonnet", "opus", "fable"):
            out["model"] = m
        else:
            problems.append(f'{out["id"]}: model must be sonnet, opus or fable (got "{r["model"]}")')
    if r.get("effort") not in (None, ""):
        e = str(r["effort"]).lower().strip()
        if e in ("low", "medium", "high", "xhigh", "max"):
            out["effort"] = e
        else:
            problems.append(f'{out["id"]}: effort must be low, medium, high, xhigh or max (got "{r["effort"]}")')
    return {"routine": out, "problems": problems}


def load(brain_path: Path, agents: list) -> dict:
    p = file(brain_path)
    doc = _read_json(p, None)
    if isinstance(doc, list):
        lst = doc
    elif isinstance(doc, dict) and isinstance(doc.get("routines"), list):
        lst = doc["routines"]
    else:
        lst = []
    routines: list[dict] = []
    problems: list[str] = []
    if doc is not None and not isinstance(doc, list) and not isinstance(doc.get("routines"), list):
        problems.append(f'{p}: expected {{"routines": [...]}}')
    for r in lst:
        v = validate(r, agents, routines)
        if v["problems"]:
            problems.extend(v["problems"])
        else:
            routines.append(v["routine"])
    return {"routines": routines, "problems": problems, "path": p, "exists": p.exists()}


def save(brain_path: Path, routines: list[dict]) -> Path:
    p = file(brain_path)
    p.parent.mkdir(parents=True, exist_ok=True)
    clean = []
    for r in routines:
        c = {"id": r["id"], "dept": r["dept"], "agent": r["agent"], "title": r["title"], "text": r["text"],
             "when": r["when"], "needsOk": r["needsOk"], "paused": r["paused"]}
        if r.get("model"):
            c["model"] = r["model"]
        if r.get("effort"):
            c["effort"] = r["effort"]
        if r.get("plan"):
            c["plan"] = r["plan"]
        clean.append(c)
    p.write_text(json.dumps({"routines": clean}, indent=2) + "\n")
    return p


def with_state(routines: list[dict], st: dict, now: float | None = None) -> dict:
    import time
    now = now if now is not None else time.time() * 1000
    changed = False
    out = []
    for r in routines:
        s = st.setdefault(r["id"], {})
        if not s.get("nextAt") or s.get("when") != json.dumps(r["when"]):
            s["nextAt"] = next_run(r["when"], now)
            s["when"] = json.dumps(r["when"])
            changed = True
        out.append({**r, "desc": describe(r["when"]), "nextAt": None if r["paused"] else s["nextAt"],
                    "lastAt": s.get("lastAt"), "runs": s.get("runs", 0), "lastTaskId": s.get("lastTaskId"),
                    "lastLate": bool(s.get("lastLate"))})
    for rid in list(st.keys()):
        if not any(r["id"] == rid for r in routines):
            del st[rid]
            changed = True
    return {"list": out, "changed": changed}


def due(routines: list[dict], st: dict, now: float | None = None) -> list[dict]:
    import time
    now = now if now is not None else time.time() * 1000
    hits = []
    for r in routines:
        if r["paused"]:
            continue
        s = st.get(r["id"])
        if not s or not s.get("nextAt"):
            continue
        if s["nextAt"] <= now:
            hits.append({"routine": r, "due": s["nextAt"], "late": (now - s["nextAt"]) > LATE_AFTER})
    return hits


def advance(st: dict, r: dict, now: float | None = None, task_id: str | None = None, late: bool = False) -> dict:
    import time
    now = now if now is not None else time.time() * 1000
    s = st.setdefault(r["id"], {})
    s["lastAt"] = now
    s["runs"] = s.get("runs", 0) + 1
    s["lastTaskId"] = task_id
    s["lastLate"] = late
    s["nextAt"] = next_run(r["when"], now)
    return s


def guess_needs_ok(text: str) -> bool:
    t = str(text).lower()
    outbound = bool(re.search(r"\b(send|sends|email them|reply to|replies|respond|chase|nudge|remind|reminder|post|publish|pay|invoice them|book|schedule a|cancel|update the crm|delete|forward|message)\b", t))
    read_only = bool(re.search(r"\b(list|summari[sz]e|triage|tell me|what|report|match|reconcile|qualify|review|check|read|find|flag|count|draft)\b", t))
    if re.search(r"\bdraft\b", t) and not re.search(r"\bsend\b", t):
        return True
    return outbound or not read_only


def ask_line(task: dict) -> str:
    return f'"{task["title"]}" is done and waiting for your OK — approve to send it, reject to tell me what to change.'


def list_text(lst: list[dict], dept: str, agents: list) -> str:
    mine = [r for r in lst if r["dept"] == dept]
    if not mine:
        return f'Nothing on the {NAMES[dept]} timetable yet. Give me one with a time in it — "every weekday at 8am, …" — and I will put it on.'

    def name(aid):
        a = next((x for x in agents if x.id == aid), None)
        return a.name if a else aid

    lines = [
        f'• {r["title"]} — {r["desc"]} · {name(r["agent"])}' + (" · PAUSED" if r["paused"] else "") + (" · waits for your OK" if r["needsOk"] else " · read-only")
        for r in mine
    ]
    return f"{NAMES[dept]} routines:\n" + "\n".join(lines) + '\n\nSay "pause …", "resume …", "run … now" or "delete …" with a few words from the name.'


def match_routine(lst: list[dict], dept: str, words: str) -> dict | None:
    w = [x for x in re.split(r"[^a-z0-9]+", str(words).lower()) if len(x) > 2 and x not in ("the", "one", "now", "routine", "and", "please")]
    best = None
    best_n = 0
    for r in [r for r in lst if r["dept"] == dept]:
        hay = f'{r["title"]} {r["text"]} {r["desc"]} {r["when"].get("at", "")}'.lower()
        n = sum(1 for x in w if x in hay)
        if n > best_n:
            best_n = n
            best = r
    return best if best_n else None
