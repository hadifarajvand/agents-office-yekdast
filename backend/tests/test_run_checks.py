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
    assert [c["ok"] for c in r] == [True, True, True, False]
    assert len(r[0]["detail"]) <= 2500
