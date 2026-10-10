"""The task integrity check: read-only, and it names exactly the faults that make the lists disagree.

Each test seeds one fault into otherwise clean data and expects that code (and only that code).
Nothing here may write: the check reports, the owner decides (MASTER_PLAN Part G, S3).
"""
from __future__ import annotations

import copy

from fastapi.testclient import TestClient

from app import taskcheck
from app.main import app

SEATS = {"exec-ceo-strategist", "exec-vp-engineering", "sec-compliance"}


def task(tid="t1", **kw):
    t = {"id": tid, "dept": "exec", "agent": "exec-ceo-strategist", "state": "done", "title": "x", "result": "ok"}
    t.update(kw)
    return t


def pl(tid, **kw):
    base = {"by": "pipeline", "pipeline": True, "jobId": "j1", "stage": "build"}
    base.update(kw)
    return task(tid, **base)


JOBS = [{"id": "j1", "status": "running"}]


def codes(report):
    return sorted(f["code"] for f in report["findings"])


def test_clean_data_reports_nothing_and_counts_everything():
    r = taskcheck.check([task("a"), task("b", state="next"), pl("pl-j1-build-x-work-a0-1", state="doing")], JOBS, SEATS)
    assert r["ok"] is True and r["findings"] == []
    assert r["total"] == 3 and r["byState"] == {"done": 1, "next": 1, "doing": 1}
    assert r["visible"] == 3 and r["hiddenFormerSeat"] == 0


def test_failed_rows_are_counted_separately_from_done():
    r = taskcheck.check([task("a"), task("b", error=True, result="boom")], JOBS, SEATS)
    assert r["failed"] == 1 and r["ok"] is True


def test_a_failed_row_without_a_reason_is_reported():
    r = taskcheck.check([task("a", error=True, result="")], JOBS, SEATS)
    assert codes(r) == ["failed_without_reason"] and r["findings"][0]["ids"] == ["a"]


def test_rows_of_a_former_seat_are_reported_and_counted_as_hidden():
    r = taskcheck.check([task("a"), task("b", agent="olead"), task("c", agent="dlead")], JOBS, SEATS)
    assert codes(r) == ["former_seat"]
    assert r["hiddenFormerSeat"] == 2 and r["visible"] == 1 and r["total"] == 3
    assert r["ok"] is True  # history is preserved; this is a warning, not damage


def test_an_unknown_state_and_a_missing_field_are_errors():
    r = taskcheck.check([task("a", state="weird"), task("b", agent=""), task("c", dept=None)], JOBS, SEATS)
    assert codes(r) == ["bad_state", "missing_field"]
    assert r["ok"] is False
    assert {f["code"]: f["count"] for f in r["findings"]} == {"bad_state": 1, "missing_field": 2}


def test_a_pipeline_row_whose_job_is_gone_is_an_orphan():
    r = taskcheck.check([pl("p1", jobId="gone")], JOBS, SEATS)
    assert codes(r) == ["orphan_pipeline_row"]


def test_a_doing_pipeline_row_of_a_job_that_is_not_running_is_stale():
    jobs = [{"id": "j1", "status": "parked"}]
    r = taskcheck.check([pl("p1", state="doing"), pl("p2", state="done")], jobs, SEATS)
    assert codes(r) == ["stale_doing_row"] and r["findings"][0]["ids"] == ["p1"]


def test_the_same_attempt_written_twice_is_a_duplicate_but_a_retry_after_a_park_is_not():
    a = pl("pl-j1-build-lead-work-a0-1", attempt=0, parks=0)
    dup = pl("pl-j1-build-lead-work-a0-2", attempt=0, parks=0)
    retry = pl("pl-j1-build-lead-work-a0-3", attempt=0, parks=1)
    assert codes(taskcheck.check([a, dup], JOBS, SEATS)) == ["duplicate_pipeline_row"]
    assert codes(taskcheck.check([a, retry], JOBS, SEATS)) == []


def test_rows_from_before_attempts_existed_are_never_called_duplicates():
    old1, old2 = pl("pl-j1-build-lead-work-1"), pl("pl-j1-build-lead-work-2")
    assert codes(taskcheck.check([old1, old2], JOBS, SEATS)) == []


def test_findings_list_at_most_ten_ids_but_count_all():
    many = [task(f"t{i}", agent="olead") for i in range(25)]
    f = taskcheck.check(many, JOBS, SEATS)["findings"][0]
    assert f["count"] == 25 and len(f["ids"]) == 10


def test_the_check_never_changes_its_input():
    data = [task("a", agent="olead"), pl("p1", state="doing", jobId="gone"), task("c", state="weird")]
    before = copy.deepcopy(data)
    jobs = [{"id": "j1", "status": "parked"}]
    taskcheck.check(data, jobs, SEATS)
    assert data == before and jobs == [{"id": "j1", "status": "parked"}]


def test_the_route_reports_the_stored_rows_and_writes_nothing(fake_db):
    import asyncio
    for t in (task("a"), task("b", agent="olead"), pl("p1", state="doing", jobId="gone")):
        asyncio.run(fake_db.save_task(t))
    before = copy.deepcopy(fake_db.tasks)
    c = TestClient(app, headers={"X-AO-Client": "office", "Origin": "http://localhost:4520"})
    r = c.get("/api/tasks/integrity")
    assert r.status_code == 200
    body = r.json()
    assert body["total"] == 3 and body["hiddenFormerSeat"] == 1
    assert codes(body) == ["former_seat", "orphan_pipeline_row"]
    assert fake_db.tasks == before
