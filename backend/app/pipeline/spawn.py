"""A department lead may spawn a bench role as a bounded sub-agent.

The bench (seed/bench.json) is a list of Citadel roles that are not seats. A lead can call one
inside a job stage to get a draft or a finding. Rules, enforced here and nowhere else:
only a lead, only from its own department's bench, at most `spawn.max_per_stage` per job stage,
depth 1 (a sub-agent cannot spawn), the cost lands on the job's meter, and the result is
information only: a sub-agent never records a verdict, an approval or an exposure decision.
The call is written to the audit log before the model runs.
"""
from __future__ import annotations

import contextvars
import json
from pathlib import Path

from .. import db
from ..config import load_config
from ..llm import ask
from ..roster import defaults

_BENCH_PATH = Path(__file__).resolve().parent.parent / "seed" / "bench.json"
_in_spawn: contextvars.ContextVar[bool] = contextvars.ContextVar("in_spawn", default=False)


class SpawnRefused(Exception):
    pass


def bench() -> dict[str, list[dict]]:
    return json.loads(_BENCH_PATH.read_text())["bench"]


def limits() -> dict:
    return {"max_per_stage": 3, **(load_config().pipeline.get("spawn") or {})}


async def spawn(lead_id: str, bench_id: str, task: str, *, job_id: str, stage: str) -> dict:
    """Returns {ok, bench_id, text, evidence_id}. Raises SpawnRefused for a rule breach."""
    if _in_spawn.get():
        raise SpawnRefused("a sub-agent cannot spawn another (depth is 1)")
    seat = next((a for a in defaults() if a.id == lead_id), None)
    if seat is None or not seat.lead:
        raise SpawnRefused(f'"{lead_id}" is not a department lead')
    from . import exposure as exp
    if not exp.is_live(load_config(), seat.department):
        raise SpawnRefused(f"{seat.department} is not live")
    role = next((b for b in bench().get(seat.department, []) if b["citadel_id"] == bench_id), None)
    if role is None:
        raise SpawnRefused(f'"{bench_id}" is not on the {seat.department} bench')
    if not str(task or "").strip():
        raise SpawnRefused("a task is required")
    used = [e for e in await db.list_evidence(job_id) if e["kind"] == "spawn" and e["stage"] == stage]
    cap = int(limits()["max_per_stage"])
    if len(used) >= cap:
        raise SpawnRefused(f"{stage} already used its {cap} sub-agents")

    await db.audit(lead_id, seat.department, "spawn", bench_id, f"{job_id}/{stage}", True)
    system = (f"You are {role['name']}, a specialist sub-agent working for the {seat.name} of an internal "
              f"software workshop. Your remit: {role['description']}. Answer the task concisely. You give "
              "information only: you do not approve, pass or fail anything, and you do not act outside this "
              "reply.")
    tok = _in_spawn.set(True)
    try:
        text = await ask(system, str(task)[:4000], role="research", max_tokens=1500)
    finally:
        _in_spawn.reset(tok)
    eid = await db.add_evidence(job_id, stage, "spawn", f"{bench_id} (spawned by {lead_id})", None, text[:4000])
    return {"ok": True, "bench_id": bench_id, "text": text, "evidence_id": eid}


async def consult(from_lead: str, to_lead: str, question: str, *, job_id: str, stage: str) -> dict:
    """A lead asks another department's lead a question. Read-only: the answer is information
    (evidence kind \"consult\"), the answering lead gains no say in this stage's verdict."""
    from ..context import build_pack, fence
    a = next((x for x in defaults() if x.id == from_lead), None)
    b = next((x for x in defaults() if x.id == to_lead), None)
    if not a or not a.lead or not b or not b.lead:
        raise SpawnRefused("both sides of a consult must be department leads")
    if a.department == b.department:
        raise SpawnRefused("consult another department; use your own seats for your own questions")
    from . import exposure as exp
    for who in (a, b):
        if not exp.is_live(load_config(), who.department):
            raise SpawnRefused(f"{who.department} is not live")
    if not str(question or "").strip():
        raise SpawnRefused("a question is required")
    used = [e for e in await db.list_evidence(job_id) if e["kind"] == "consult" and e["stage"] == stage]
    if len(used) >= 2:
        raise SpawnRefused(f"{stage} already used its 2 consults")
    await db.audit(from_lead, a.department, "consult", to_lead, f"{job_id}/{stage}", True)
    system = (await build_pack(to_lead, stage=stage, query=question)) + (
        f"\n\nThe {a.name} asks you a question about this job. Answer briefly from your department's point of view. "
        "You are not deciding anything; you give information only.")
    text = await ask(system, fence(str(question)[:3000], "consult question"), role="research", max_tokens=1000)
    eid = await db.add_evidence(job_id, stage, "consult", f"{to_lead} answers {from_lead}", None, text[:4000])
    return {"ok": True, "from": from_lead, "to": to_lead, "text": text, "evidence_id": eid}
