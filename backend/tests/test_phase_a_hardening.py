"""Regression tests for the Phase A audit findings (redaction gaps, audit-log
forgery, skills crash when the brain lives outside the app root)."""
import pytest

from app import policy
from app.skills import load_skills


@pytest.mark.parametrize("raw,secret", [
    ("{'api_key': 'sk-ant-abc123def456', 'x': 1}", "sk-ant-abc123def456"),
    ('{"token": "ghp_abcdefghijklmnop1234"}', "ghp_abcdefghijklmnop1234"),
    ("Authorization: Basic dXNlcjpwYXNzd29yZA==", "dXNlcjpwYXNzd29yZA=="),
    ("secret=topsecretvalue", "topsecretvalue"),
    ("the password is hunter2", "hunter2"),
    ("pushed with ghp_abcdefghijklmnop1234 today", "ghp_abcdefghijklmnop1234"),
])
def test_redact_secrets_catches_structured_and_prefixed_secrets(raw, secret):
    assert secret not in policy.redact_secrets(raw)
    assert secret not in policy.redact(raw)


def test_redact_secrets_keeps_pii_in_deliverables():
    draft = "Reply to bob@acme.com or call 555-123-4567."
    assert policy.redact_secrets(draft) == draft
    assert "bob@acme.com" not in policy.redact(draft)  # log redaction still hides it


def test_audit_log_line_cannot_be_forged_with_newlines():
    line = policy.audit_log_line("a", "devops", "github", "read",
                                 "repo\n2099-01-01 | evil (exec) | x | y | z | ✓allowed", True)
    assert "\n" not in line and "\r" not in line


def test_skills_load_when_brain_is_outside_app_root(tmp_path):
    skill_dir = tmp_path / "Agents Office" / "skills" / "demo"
    skill_dir.mkdir(parents=True)
    (skill_dir / "SKILL.md").write_text("---\nname: demo\ndescription: d\n---\n# Demo\nUse this for demos.\n")
    skills = load_skills(tmp_path, [])  # must not raise ValueError from relative_to(ROOT)
    assert any(s.name == "demo" for s in skills.skills)
    assert any(s.path.endswith("SKILL.md") for s in skills.skills if s.name == "demo")
