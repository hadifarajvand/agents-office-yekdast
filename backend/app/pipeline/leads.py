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
    '{"verdict":"PASS"|"FAIL","reasons":["..."],"cites":["<evidence id>", ...]}'
)


def _fmt(e: dict) -> str:
    ok = {True: "ok", False: "FAILED", None: "info"}[e.get("ok")]
    body = str(e.get("body"))[:1200]
    return f'- id={e["id"]} [{e["kind"]}] {e["title"]} ({ok}): {body}'


async def review(stage: str, lead_id: str, lead_label: str, job: dict, evidence: list[dict], *,
                 criteria: str = "", role: str = "lead_review") -> dict:
    """Returns {verdict, reasons, cites, actor}. Never raises on model output problems."""
    mine = [e for e in evidence if e["stage"] == stage]
    failed = [e for e in mine if e.get("ok") is False]
    if failed:
        return {"verdict": "FAIL", "actor": lead_id, "cites": [e["id"] for e in failed],
                "reasons": [f'check failed: {e["title"]}' for e in failed]}
    if not mine:
        return {"verdict": "FAIL", "actor": lead_id, "cites": [], "reasons": ["no evidence was produced for this stage"]}

    user = (f"Stage: {stage}\nYou are: {lead_label}\nJob: {job.get('title')}\n"
            f"Client brief: {str(job.get('brief'))[:2000]}\nCriteria: {criteria or 'the stage did what it was asked'}\n\n"
            "Evidence:\n" + "\n".join(_fmt(e) for e in mine))
    meter = RunMeter(label=f'job:{job["id"]}:{stage}:review')
    tok = current_meter.set(meter)
    try:
        data = await get_deps().chat_json(SYSTEM, user, role=role)
    except Exception as exc:  # unparsable or unreachable model: a lead that cannot answer does not pass
        return {"verdict": "FAIL", "actor": lead_id, "cites": [], "reasons": [f"review failed: {type(exc).__name__}"]}
    finally:
        current_meter.reset(tok)

    if not meter.valid:
        return {"verdict": "FAIL", "actor": lead_id, "cites": [],
                "reasons": ["review void: " + "; ".join(meter.mismatches)]}
    verdict = str(data.get("verdict", "")).upper()
    reasons = [str(r)[:300] for r in (data.get("reasons") or [])][:6]
    ids = {e["id"] for e in mine}
    cites = [c for c in (data.get("cites") or []) if c in ids]
    if verdict == "PASS" and not cites:
        return {"verdict": "FAIL", "actor": lead_id, "cites": [], "reasons": ["PASS without citing evidence"] + reasons}
    if verdict not in ("PASS", "FAIL"):
        return {"verdict": "FAIL", "actor": lead_id, "cites": cites, "reasons": ["unclear verdict"] + reasons}
    return {"verdict": verdict, "actor": lead_id, "cites": cites, "reasons": reasons}
