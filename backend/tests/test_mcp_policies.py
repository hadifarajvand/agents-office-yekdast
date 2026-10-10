"""The owner's `policies` block is enforced at call time, not just read."""
from pathlib import Path

import pytest

from app import config, policy
from app.mcp import MCPRegistry

POLICIES = {
    "secrets": {"source": "env", "inlineSecretsForbidden": True},
    "mcpAccessNotes": {
        "github": "read-only", "gitlab": "issue writes need approval", "slack": "no broadcasts",
        "gmail": "draft only", "notion": "no deletes", "docker": "logs and inspect only",
        "prometheus": "reads", "grafana": "reads",
        "requireHumanApprovalForWrites": ["gmail", "gitlab"],
        "auditLog": "./brain-yekdast/audit/mcp-access.log",
    },
}


def verdict(server, tool, args=None, mode="draft", pol=POLICIES):
    return policy.tool_verdict(server, tool, args, mode, pol)


@pytest.mark.parametrize("server,tool", [
    ("github", "merge_pull_request"), ("github", "create_issue"), ("github", "add_issue_comment"),
    ("prometheus", "create_silence"), ("grafana", "update_dashboard"),
    ("docker", "run_container"), ("docker", "exec_command"), ("docker", "list_containers"),
    ("notion", "delete_page"), ("gmail", "send_message"), ("gmail", "sendDraft"),
])
def test_refused(server, tool):
    assert verdict(server, tool, mode="approve" if server == "gmail" else "draft")


@pytest.mark.parametrize("server,tool", [
    ("github", "list_pull_requests"), ("github", "get_file_contents"), ("github", "search_code"),
    ("docker", "container_logs"), ("docker", "inspect_container"), ("prometheus", "query_range"),
    ("grafana", "get_dashboard"), ("notion", "search_pages"), ("notion", "create_page"),
    ("gitlab", "list_issues"), ("gmail", "search_threads"),
])
def test_allowed(server, tool):
    assert verdict(server, tool) is None


def test_writes_need_the_owners_approval_at_the_gate():
    assert "approval" in verdict("gitlab", "create_issue", mode="draft")
    assert verdict("gitlab", "create_issue", mode="approve") is None
    assert "approval" in verdict("gmail", "create_draft", mode="routine")
    assert verdict("gmail", "create_draft", mode="approve") is None
    assert verdict("gmail", "send_message", mode="approve")  # draft-only, even when approved


def test_slack_broadcasts_refused_but_messages_allowed():
    assert verdict("slack", "send_message", {"text": "heads up @channel"})
    assert verdict("slack", "send_message", {"text": "ping @here please"})
    assert verdict("slack", "send_message", {"text": "mail me at a@everyone.example"}) is None
    assert verdict("slack", "send_message", {"text": "done, thanks"}) is None


def test_a_connector_with_no_note_gets_no_extra_rule():
    assert verdict("github", "merge_pull_request", pol={}) is None
    assert verdict("github", "merge_pull_request", pol={"mcpAccessNotes": {"slack": "x"}}) is None


def test_call_allowed_applies_policy_after_the_wiring_check(monkeypatch):
    reg = MCPRegistry()
    reg.configure({"allow": ["github"], "deny": [], "departments": {"github": ["engineering"]}})
    reg.attach_tools("github", [], name="github")
    monkeypatch.setattr(config, "load_config", lambda: type("C", (), {"policies": POLICIES})())
    ok, _ = reg.call_allowed("engineering", "github", "list_pull_requests", {}, "draft")
    assert ok
    ok, msg = reg.call_allowed("engineering", "github", "merge_pull_request", {}, "draft")
    assert not ok and "read-only" in msg
    ok, msg = reg.call_allowed("fin", "github", "list_pull_requests", {}, "draft")
    assert not ok and "not wired" in msg


def test_audit_log_follows_the_owners_path_only_for_the_office_brain(tmp_path, monkeypatch):
    brain = tmp_path / "brain"
    brain.mkdir()
    cfg = type("C", (), {"policies": POLICIES, "brain_path": brain})()
    monkeypatch.setattr(config, "load_config", lambda: cfg)
    assert policy.audit_log_path(brain) == (config.ROOT / "brain-yekdast" / "audit" / "mcp-access.log").resolve()
    other = tmp_path / "other"
    assert policy.audit_log_path(other) == other / "Agents Office" / "audit" / "mcp-access.log"


def test_inline_secret_in_an_env_setting_is_reported_without_echoing_it():
    merged = {"policies": POLICIES, "router": {"api_key_env": "sk-live-abc123XYZ", "format": "openai"},
              "notify": {"telegram_token_env": "TELEGRAM_BOT_TOKEN"}}
    problems = config._inline_secret_problems(merged)
    assert problems == ["router.api_key_env must be an environment variable NAME, not a value — cleared"]
    assert merged["router"]["api_key_env"] == "" and merged["notify"]["telegram_token_env"] == "TELEGRAM_BOT_TOKEN"
    assert "sk-live" not in " ".join(problems)


def test_secret_check_is_off_unless_the_owner_turns_it_on():
    merged = {"policies": {}, "router": {"api_key_env": "sk-live-abc123XYZ"}}
    assert config._inline_secret_problems(merged) == []


def test_policies_is_a_known_config_key():
    assert "policies" in config.KNOWN_KEYS
    assert not any("policies" in p for p in config.load_config().problems)
