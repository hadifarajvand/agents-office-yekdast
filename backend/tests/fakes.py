"""In-memory stand-ins for app.db and the model layer, so tests need no Postgres and
no router. FakeDB implements every public coroutine in app/db.py with the same
signature; install() monkeypatches them all."""
from __future__ import annotations

import time
import uuid

from app import db


class FakeDB:
    def __init__(self):
        self.tasks: dict[str, dict] = {}
        self.routine_state: dict = {}
        self.jobs: dict[str, dict] = {}
        self.approvals: dict[tuple, dict] = {}
        self.evidence: dict[str, dict] = {}
        self.audit_rows: list[dict] = []
        self.costs: list[dict] = []
        self.counters: dict[str, int] = {}

    # tasks
    async def list_tasks(self):
        return sorted((dict(t) for t in self.tasks.values()), key=lambda t: t.get("createdAt", 0))

    async def get_task(self, task_id):
        t = self.tasks.get(task_id)
        return dict(t) if t else None

    async def save_task(self, task):
        self.tasks[task["id"]] = dict(task)

    async def claim_task(self, task_id, from_state, to_state):
        t = self.tasks.get(task_id)
        if not t or t.get("state") != from_state:
            return None
        t["state"] = to_state
        return dict(t)

    async def delete_task(self, task_id):
        self.tasks.pop(task_id, None)

    async def fail_interrupted_tasks(self):
        n = 0
        for t in self.tasks.values():
            if t.get("state") == "doing":
                t.update(state="done", error=True)
                n += 1
        return n

    # routines
    async def load_routine_state(self):
        return {k: dict(v) for k, v in self.routine_state.items()}

    async def save_routine_state(self, st):
        self.routine_state = {k: dict(v) for k, v in st.items()}

    async def claim_routine_slot(self, routine_id, due):
        key = f"routine-due:{routine_id}:{int(due)}"
        if key in self.counters:
            return False
        self.counters[key] = 1
        return True

    # jobs
    async def save_job(self, job):
        self.jobs[job["id"]] = dict(job)

    async def get_job(self, job_id):
        j = self.jobs.get(job_id)
        return dict(j) if j else None

    async def list_jobs(self):
        return sorted((dict(j) for j in self.jobs.values()), key=lambda j: j.get("createdAt", 0))

    async def record_approval(self, job_id, stage, role, verdict, note, evidence, actor):
        key = (job_id, stage, role)
        if key in self.approvals:
            return False
        self.approvals[key] = {"job_id": job_id, "stage": stage, "role": role, "verdict": verdict,
                               "note": note, "evidence": evidence, "actor": actor, "at": time.time() * 1000}
        return True

    async def clear_approvals(self, job_id, stage):
        for k in [k for k in self.approvals if k[0] == job_id and k[1] == stage]:
            del self.approvals[k]

    async def list_approvals(self, job_id):
        return [dict(v) for k, v in self.approvals.items() if k[0] == job_id]

    async def add_evidence(self, job_id, stage, kind, title, ok, body, evidence_id=None):
        eid = evidence_id or uuid.uuid4().hex[:12]
        self.evidence[eid] = {"id": eid, "job_id": job_id, "stage": stage, "kind": kind, "title": title,
                              "ok": ok, "body": body, "at": time.time() * 1000}
        return eid

    async def list_evidence(self, job_id):
        return [dict(e) for e in self.evidence.values() if e["job_id"] == job_id]

    # audit, costs, counters
    async def audit(self, agent, dept, server, operation, resource, allowed, reason=""):
        self.audit_rows.append(dict(agent=agent, dept=dept, server=server, operation=operation,
                                    resource=resource, allowed=allowed, reason=reason))

    async def record_cost(self, label, model_pinned, model_seen, input_tokens, output_tokens, usd):
        self.costs.append(dict(label=label, model_pinned=model_pinned, model_seen=model_seen,
                               input_tokens=input_tokens, output_tokens=output_tokens, usd=usd))

    async def usage_window(self, hours=5.0):
        now = time.time() * 1000
        return {"runs": len(self.costs), "tokens": sum(c["input_tokens"] + c["output_tokens"] for c in self.costs),
                "usd": sum(c["usd"] for c in self.costs), "startedAt": now, "resetsAt": now + hours * 3600 * 1000}

    async def counter(self, name):
        return self.counters.get(name, 0)

    async def bump_counter(self, name):
        self.counters[name] = self.counters.get(name, 0) + 1
        return self.counters[name]

    def install(self, monkeypatch):
        for name in ("list_tasks", "get_task", "save_task", "claim_task", "delete_task", "fail_interrupted_tasks",
                     "load_routine_state", "save_routine_state", "claim_routine_slot", "save_job", "get_job",
                     "list_jobs", "record_approval", "clear_approvals", "list_approvals", "add_evidence",
                     "list_evidence", "audit", "record_cost", "usage_window", "counter", "bump_counter"):
            monkeypatch.setattr(db, name, getattr(self, name))
        return self
