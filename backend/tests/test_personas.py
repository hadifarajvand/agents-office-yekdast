"""The vendored Citadel personas: read as they are, mapped to seats, never granting tools."""
from app import personas as pe
from app.pipeline import spawn as sp


def test_the_four_live_departments_are_vendored_whole():
    counts = {d: len(pe.all_personas(d)) for d in ("exec", "engineering", "secdata", "devops")}
    assert counts == {"exec": 20, "engineering": 25, "secdata": 40, "devops": 50}
    assert len(pe.all_personas()) == 135


def test_a_persona_keeps_the_whole_file_verbatim():
    p = pe.get("exec-ceo-strategist")
    assert p.name == "CEO Strategist" and p.dept == "exec" and p.tier == "reasoning_deep" and p.rag
    assert "Stay within your domain" in p.system_prompt and "Retrieve chunks" in p.rag_prompt
    assert p.source == "agents/executive/exec-ceo-strategist.md"


def test_citadel_personas_grant_no_tools_so_nothing_here_can_widen_a_seat():
    # Measured at the vendored commit: every department persona has tools: [] and skills: [].
    assert all(p.tools == () and p.skills == () for p in pe.all_personas())


def test_the_hand_written_subagents_carry_real_allowlists():
    hands = {h.id: h for h in pe.hand_agents()}
    assert len(hands) == 11 and hands["code-reviewer"].tools == ("Read", "Grep", "Glob")


def test_every_live_seat_with_a_citadel_id_resolves_to_a_vendored_persona():
    assert pe.for_seat("exec-ceo-strategist").id == "exec-ceo-strategist"
    from app.roster import defaults
    live = {"exec", "engineering", "secdata", "devops"}
    missing = [a.id for a in defaults() if a.department in live and pe._seat_ids().get(a.id) and not pe.for_seat(a.id)]
    assert missing == []


def test_every_bench_role_in_the_live_departments_has_a_persona():
    gaps = [b["citadel_id"] for d in ("exec", "engineering", "secdata", "devops") for b in sp.bench()[d] if not pe.get(b["citadel_id"])]
    assert gaps == []


def test_tiers_resolve_to_the_one_free_model():
    assert {pe.model_for(t) for t in ("reasoning_deep", "reasoning_fast", "cheap_fast", "unknown")} == {"oc/nemotron-3-ultra-free"}
