"""Task 6: the 9-stage cross-department approval workflow from .claude/AGENTS.md
(spec->architecture->data design->security review->code review->build->staging->
production->verify) modeled as explicit states/transitions in graph/engine.py,
rather than left to prompt text — so a task's stage transitions are enforced
code-side instead of trusted to the model.
"""
from __future__ import annotations

from app.graph.engine import APPROVAL_STAGES, next_approval_stage, validate_stage_transition


def test_nine_stages_in_order():
    assert APPROVAL_STAGES == [
        "spec", "architecture", "data_design", "security_review",
        "code_review", "build", "staging", "production", "verify",
    ]


def test_next_stage_follows_the_chain():
    assert next_approval_stage("spec") == "architecture"
    assert next_approval_stage("code_review") == "build"
    assert next_approval_stage("verify") is None


def test_sequential_transition_is_valid():
    ok, reason = validate_stage_transition("spec", "architecture")
    assert ok is True
    assert reason == ""


def test_skipping_stages_is_rejected():
    ok, reason = validate_stage_transition("spec", "build")
    assert ok is False
    assert 'next stage must be "architecture"' in reason


def test_going_backwards_is_rejected():
    ok, reason = validate_stage_transition("code_review", "spec")
    assert ok is False
    assert "next stage must be" in reason


def test_last_stage_has_no_next():
    ok, reason = validate_stage_transition("verify", "spec")
    assert ok is False
    assert "last stage" in reason


def test_unknown_stage_rejected():
    ok, reason = validate_stage_transition("spec", "deployment")
    assert ok is False
    assert "not one of the approval stages" in reason

    ok, reason = validate_stage_transition("not-a-stage", "spec")
    assert ok is False
    assert "not one of the approval stages" in reason
