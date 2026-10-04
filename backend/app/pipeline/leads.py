"""A department lead's review of a stage. The lead is a model, so its verdict is only
trusted when it is backed by evidence: a PASS must cite at least one evidence id that
exists for this job and stage, any failed deterministic check is an automatic FAIL
(no model call), and a verdict produced by a different model than the one pinned is
void."""
from __future__ import annotations

from ..llm import RunMeter, current_meter
from .ports import get_deps

SYSTEM = (
    "You are the lead reviewing your own team's stage of a client job. Decide PASS or FAIL against the "
    "acceptance criteria. You may only PASS if the evidence supports it, and you must cite the evidence "
    "ids you relied on. Evidence marked ok=false is a failure. Reply with JSON only: "
    '{"verdict":"PASS"|"FAIL","reasons":["..."],"cites":["<evidence id>", ...]}. '
    "If you need a specialist's opinion first, instead reply {\"spawn\":[{\"bench\":\"<id>\",\"task\":\"...\"}]} "
    "naming up to 3 of the bench roles you were offered; you will then see their answers and must decide."
)


def _fmt(e: dict) -> str:
    ok = {True: "ok", False: "FAILED", None: "info"}[e.get("ok")]
    body = str(e.get("body"))[:1200]
    return f'- id={e["id"]} [{e["kind"]}] {e["title"]} ({ok}): {body}'


def _detail(e: dict) -> str:
    """The end of a failed check's output, so the retry knows what broke (not just that it broke)."""
    d = str((e.get("body") or {}).get("detail") or "").strip()
    return f" — {d[-400:]}" if d else ""


def _dept_of(lead_id: str) -> str:
    from ..context import seat
    a = seat(lead_id)
    return a.department if a else ""


async def review(stage: str, lead_id: str, lead_label: str, job: dict, evidence: list[dict], *,
                 criteria: str = "", role: str = "lead_review") -> dict:
    """Returns {verdict, reasons, cites, actor}. Never raises on model output problems."""
    mine = [e for e in evidence if e["stage"] == stage]
    failed = [e for e in mine if e.get("ok") is False]
    if failed:
        return {"verdict": "FAIL", "actor": lead_id, "cites": [e["id"] for e in failed],
                "reasons": [f'check failed: {e["title"]}' + _detail(e) for e in failed]}
    if not mine:
        return {"verdict": "FAIL", "actor": lead_id, "cites": [], "reasons": ["no evidence was produced for this stage"]}

    user = (f"Stage: {stage}\nYou are: {lead_label}\nJob: {job.get('title')}\n"
            f"Client brief: {str(job.get('brief'))[:2000]}\nCriteria: {criteria or 'the stage did what it was asked'}\n\n"
            "Evidence:\n" + "\n".join(_fmt(e) for e in mine))
    meter = RunMeter(label=f'job:{job["id"]}:{stage}:review')
    tok = current_meter.set(meter)
    try:
        from ..context import build_pack, fence
        from . import spawn as sp
        from ..config import load_config
        spawn_on = bool((load_config().pipeline.get("spawn") or {}).get("enabled"))
        offered = [f'{b["citadel_id"]} ({b["description"]})' for b in sp.bench().get(_dept_of(lead_id), [])][:25] if spawn_on else []
        system = await build_pack(lead_id, stage=stage, query=str(job.get("title", ""))) + "\n\n" + SYSTEM
        if offered:
            system += "\nBench roles you may spawn: " + "; ".join(offered)
        user = user.replace(f"Client brief: {str(job.get('brief'))[:2000]}", "Client brief: " + fence(str(job.get("brief"))[:2000]))
        data = await get_deps().chat_json(system, user, role=role)
        if isinstance(data, dict) and data.get("spawn") and "verdict" not in data:
            notes = []
            for req in list(data["spawn"])[:3]:
                try:
                    r = await sp.spawn(lead_id, str(req.get("bench", "")), str(req.get("task", "")), job_id=job["id"], stage=stage)
                    notes.append(f'- {r["bench_id"]} (evidence {r["evidence_id"]}): {r["text"][:600]}')
                except sp.SpawnRefused as e:
                    notes.append(f"- refused: {e}")
            data = await get_deps().chat_json(system, user + "\n\nSpecialist answers (information only):\n" + "\n".join(notes), role=role)
    except Exception as exc:  # unparsable model output: a lead that cannot answer does not pass
        from .graph import router_down
        if router_down(exc):
            raise  # the graph parks the job: an outage is not the work's fault
        return {"verdict": "FAIL", "actor": lead_id, "cites": [], "reasons": [f"review failed: {type(exc).__name__}"],
                "cost": {"tokens": meter.tokens, "usd": meter.usd}}
    finally:
        current_meter.reset(tok)
    cost = {"tokens": meter.tokens, "usd": meter.usd}

    if not meter.valid:
        return {"verdict": "FAIL", "actor": lead_id, "cites": [], "cost": cost,
                "reasons": ["review void: " + "; ".join(meter.mismatches)]}
    verdict = str(data.get("verdict", "")).upper()
    reasons = [str(r)[:300] for r in (data.get("reasons") or [])][:6]
    ids = {e["id"] for e in mine}
    cites = [c for c in (data.get("cites") or []) if c in ids]
    if verdict == "PASS" and not cites:
        return {"verdict": "FAIL", "actor": lead_id, "cites": [], "reasons": ["PASS without citing evidence"] + reasons, "cost": cost}
    if verdict not in ("PASS", "FAIL"):
        return {"verdict": "FAIL", "actor": lead_id, "cites": cites, "reasons": ["unclear verdict"] + reasons, "cost": cost}
    return {"verdict": verdict, "actor": lead_id, "cites": cites, "reasons": reasons, "cost": cost}
