"""Prototype: Citadel's SafetyGovernor wraps metered model calls behind AO_BACKBONE=1."""
import pytest

from app import backbone_bridge as bb


@pytest.fixture(autouse=True)
def _reset(monkeypatch):
    bb.reset()
    yield
    bb.reset()


def test_off_by_default(monkeypatch):
    monkeypatch.delenv("AO_BACKBONE", raising=False)
    assert bb.charge("job:build", 10**9, 99.0) is None


def test_token_ceiling_stops_the_run(monkeypatch):
    monkeypatch.setenv("AO_BACKBONE", "1")
    monkeypatch.setenv("AO_BACKBONE_MAX_TOKENS", "1000")
    assert bb.charge("job1:build", 400, 0.0) is None
    assert "Token limit" in bb.charge("job1:build", 700, 0.0)
    assert bb.charge("job2:build", 400, 0.0) is None  # budgets are per run


def test_kill_switch_halts_everything(monkeypatch):
    monkeypatch.setenv("AO_BACKBONE", "1")
    bb.governor().kill("owner test")
    assert "Kill switch" in bb.charge("any", 1, 0.0)


def test_tier_router_gives_big_pickle_for_every_role(monkeypatch):
    from app import llm
    monkeypatch.setenv("AO_BACKBONE", "1")
    for role in bb.ROLE_TIER:
        assert bb.model_for_role(role) == "oc/nemotron-3-ultra-free"
        assert llm.role_model(role) == "oc/nemotron-3-ultra-free"


def test_router_ignored_when_off(monkeypatch):
    monkeypatch.delenv("AO_BACKBONE", raising=False)
    assert bb.model_for_role("builder") is None


def test_owner_gate_levels():
    assert bb.requires_owner("deploy") and bb.requires_owner("owner")
    assert not bb.requires_owner("low")


def test_dollar_ceiling_caps_a_routine_run_but_not_a_job_stage(monkeypatch):
    monkeypatch.setenv("AO_BACKBONE", "1")
    monkeypatch.setenv("AO_BACKBONE_MAX_USD", "1")
    assert bb.charge("task:r1", 10, 0.6) is None
    assert "Cost limit" in bb.charge("task:r1", 10, 0.6)
    assert bb.charge("task:r2", 10, 0.6) is None  # budgets are per run
    assert bb.charge("job:j1:build", 10, 5.0) is None and bb.charge("job:j1:build", 10, 5.0) is None
