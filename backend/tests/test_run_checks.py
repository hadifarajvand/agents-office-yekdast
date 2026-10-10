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
