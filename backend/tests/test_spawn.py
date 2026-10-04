"""Lead-spawned bench sub-agents: who may spawn, from where, how often, and what they cannot do."""
from __future__ import annotations

import pytest

from app import llm
from app.pipeline import spawn as sp
from app.roster import defaults


@pytest.fixture
def asked(monkeypatch):
    calls = []

    async def fake_ask(system, user, **kw):
        calls.append((system, user, kw))
        return "finding: no hard-coded keys"
    monkeypatch.setattr(sp, "ask", fake_ask)
    return calls


def test_bench_is_per_department_and_never_contains_a_staffed_seat():
    b = sp.bench()
    assert set(b) == {"exec", "revenue", "engineering", "frontend", "devops", "secdata", "fin", "content"}
    ids = [r["citadel_id"] for rows in b.values() for r in rows]
    assert len(ids) == len(set(ids)) and "sec-sast" not in ids and any(r["citadel_id"] == "sec-container" for r in b["secdata"])
    assert not any(i.startswith("hr-") for i in ids)


async def test_a_lead_spawns_from_its_own_bench_and_the_call_is_audited(fake_db, asked):
    out = await sp.spawn("comply", "sec-container", "scan the Dockerfile", job_id="j1", stage="security")
    assert out["ok"] and "finding" in out["text"]
    assert fake_db.audit_rows[0]["agent"] == "comply" and fake_db.audit_rows[0]["server"] == "spawn"
    assert asked[0][2]["role"] == "research"
    ev = await fake_db.list_evidence("j1")
    assert ev[0]["kind"] == "spawn" and ev[0]["ok"] is None  # information, never a pass


async def test_only_leads_and_only_their_own_bench(fake_db, asked):
    non_lead = next(a for a in defaults() if not a.lead).id
    with pytest.raises(sp.SpawnRefused, match="not a department lead"):
        await sp.spawn(non_lead, "sec-container", "x", job_id="j", stage="security")
    with pytest.raises(sp.SpawnRefused, match="not on the secdata bench"):
        await sp.spawn("comply", "eng-api-designer", "x", job_id="j", stage="security")
    assert asked == [] and fake_db.audit_rows == []


async def test_at_most_three_per_stage_and_no_nesting(fake_db, asked, monkeypatch):
    for _ in range(3):
        await sp.spawn("comply", "sec-container", "x", job_id="j", stage="security")
    with pytest.raises(sp.SpawnRefused, match="already used its 3"):
        await sp.spawn("comply", "sec-container", "x", job_id="j", stage="security")
    await sp.spawn("comply", "sec-container", "x", job_id="j", stage="preview")  # another stage has its own budget

    async def nested(system, user, **kw):
        await sp.spawn("comply", "sec-container", "again", job_id="k", stage="security")
    monkeypatch.setattr(sp, "ask", nested)
    with pytest.raises(sp.SpawnRefused, match="depth is 1"):
        await sp.spawn("comply", "sec-container", "x", job_id="k", stage="security")
