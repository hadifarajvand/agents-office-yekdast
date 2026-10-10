"""Reading the container's check results: missing, corrupt or incomplete results never pass."""
import json

from app.checks.run import REQUIRED, read_checks


def test_missing_results_fail(tmp_path):
    r = read_checks(tmp_path)
    assert len(r) == 1 and r[0]["ok"] is False


def test_corrupt_results_fail(tmp_path):
    (tmp_path / "checks.json").write_text("{not json")
    assert read_checks(tmp_path)[0]["ok"] is False


def test_an_all_green_run_must_include_every_required_step(tmp_path):
    (tmp_path / "checks.json").write_text(json.dumps([{"name": "dependencies install", "ok": True}]))
    r = {c["name"]: c["ok"] for c in read_checks(tmp_path)}
    assert r["dependencies install"] is True
    assert all(r[n] is False for n in REQUIRED if n != "dependencies install")


def test_a_full_green_run_passes_and_only_true_counts_as_ok(tmp_path):
    rows = [{"name": n, "ok": True, "detail": "x" * 5000} for n in REQUIRED] + [{"name": "odd", "ok": "yes"}]
    (tmp_path / "checks.json").write_text(json.dumps(rows))
    r = read_checks(tmp_path)
    assert [c["ok"] for c in r] == [True] * len(REQUIRED) + [False]
    assert len(r[0]["detail"]) <= 2500


def test_an_audit_with_no_counts_fails(tmp_path):
    from app.checks.patch import audit_result
    (tmp_path / "a.json").write_text("{}")
    assert audit_result(tmp_path / "a.json")["ok"] is False


def test_a_missing_template_is_an_error(tmp_path, monkeypatch):
    import pytest
    from app.config import load_config
    from app.worker.base import seed_workspace
    monkeypatch.setitem(load_config().worker, "template", str(tmp_path / "nope"))
    ws = tmp_path / "ws"
    ws.mkdir()
    with pytest.raises(FileNotFoundError):
        seed_workspace(ws)


def test_the_fake_worker_is_green_only_inside_tests(tmp_path, monkeypatch):
    import asyncio
    from app.worker.fake import FakeWorker
    monkeypatch.delenv("PYTEST_CURRENT_TEST")
    res = asyncio.run(FakeWorker().run(tmp_path, {}, {}))
    assert res["checks"][0]["ok"] is False


def test_registry_unreachable_needs_the_install_to_be_the_only_failure():
    from app.checks.run import INSTALL, REGISTRY_UNREACHABLE, registry_unreachable
    down = {"name": INSTALL, "ok": False, "detail": f"ECONNRESET\n{REGISTRY_UNREACHABLE}"}
    assert registry_unreachable([down])
    assert not registry_unreachable([{**down, "detail": "E404 no such package"}])  # a bad package is the builder's
    assert not registry_unreachable([down, {"name": "unit tests pass (npm test)", "ok": False}])
    assert not registry_unreachable([{**down, "ok": True}])


def _run_checks_with_fake_npm(tmp_path, npm_body, extra_env=None):
    """Runs the real run-checks.mjs in a throwaway app whose `npm` is a script that logs its arguments."""
    import os
    import subprocess
    from pathlib import Path
    root = Path(__file__).resolve().parents[2]
    app, bin_dir = tmp_path / "app", tmp_path / "bin"
    app.mkdir()
    bin_dir.mkdir()
    (app / "package.json").write_text(json.dumps({"scripts": {"build": "x", "test": "x", "start": "x"}}))
    (app / "package-lock.json").write_text("{}")
    npm = bin_dir / "npm"
    npm.write_text("#!/bin/sh\necho \"$@\" >> " + str(tmp_path / "npm.log") + "\n" + npm_body)
    npm.chmod(0o755)
    env = {**os.environ, "PATH": f"{bin_dir}:{os.environ['PATH']}", "CHECKS_OUT": str(tmp_path / "checks.json"),
           "CHECKS_INSTALL_BACKOFF_MS": "0", **(extra_env or {})}
    subprocess.run(["node", str(root / "infra/sandbox/run-checks.mjs")], cwd=app, env=env, timeout=60, check=False)
    calls = (tmp_path / "npm.log").read_text().splitlines()
    return json.loads((tmp_path / "checks.json").read_text()), calls


def test_a_network_failure_is_retried_briefly_marked_and_never_falls_back_to_npm_install(tmp_path):
    from app.checks.run import registry_unreachable
    rows, calls = _run_checks_with_fake_npm(tmp_path, "echo 'npm ERR! code ECONNRESET' >&2\nexit 1\n")
    assert [c.split()[0] for c in calls] == ["ci", "ci", "ci"]  # first try plus two retries, no `npm install`
    assert all("--fetch-timeout" in c for c in calls)
    assert len(rows) == 1 and registry_unreachable(rows)


def test_a_hung_install_is_cut_off_at_the_attempt_timeout(tmp_path):
    rows, calls = _run_checks_with_fake_npm(tmp_path, "sleep 30\n", {"CHECKS_INSTALL_TIMEOUT_MS": "300", "CHECKS_INSTALL_BUDGET_MS": "1000"})
    assert rows[0]["ok"] is False and "timed out after" in rows[0]["detail"] and "[registry unreachable]" in rows[0]["detail"]
    assert 1 <= len(calls) <= 3  # the budget, not 101 minutes, bounds the step


def test_a_lockfile_mismatch_falls_back_to_npm_install_but_is_not_called_unreachable(tmp_path):
    rows, calls = _run_checks_with_fake_npm(tmp_path, "echo 'npm ERR! `npm ci` can only install with an existing package-lock.json' >&2\nexit 1\n")
    assert [c.split()[0] for c in calls] == ["ci", "install"]
    assert "[registry unreachable]" not in rows[0]["detail"]
