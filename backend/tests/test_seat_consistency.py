"""The 17 seats are the same everywhere they are written down (MASTER_PLAN Part G, G.4.4).

One list is the source: backend/app/seed/roster_seed.json. The API roster, the generated UI file and the
pipeline's lead wiring must all agree with it. EXPECTED_SEATS is a fixture that changes only when the owner
decides to change the seat list (Needs-attention row 19: keep the 17 seeded seats); no code path adds one.
"""
from __future__ import annotations

import dataclasses
import json
import re
from collections import Counter
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from app import config as config_mod
from app import roster as roster_mod
from app.roster import DEPTS, defaults, load_roster

ROOT = Path(__file__).resolve().parents[2]
EXPECTED_SEATS = [
    "exec-ceo-strategist",
    "lexi", "ilm", "piper", "enzo",
    "exec-vp-engineering",
    "mlead", "riley", "gfx",
    "devops-cd",
    "sec-compliance",
    "alead", "invo", "apay",
    "elead", "newt", "cmail",
]
EXPECTED_DEPTS = {"exec", "revenue", "engineering", "frontend", "devops", "secdata", "fin", "content"}


def seed() -> dict:
    return json.loads((ROOT / "backend/app/seed/roster_seed.json").read_text())


def generated_ui_seats() -> list[dict]:
    """Parse src/roster.gen.js (id, dept, lead) without running node."""
    text = (ROOT / "src/roster.gen.js").read_text()
    block = text.split("export const SEED_AGENTS = [", 1)[1].split("];", 1)[0]
    return [{"id": m.group(1), "dept": m.group(2), "lead": "lead:true" in m.group(0)}
            for m in re.finditer(r'\{id:"([^"]+)".*?dept:"([^"]+)".*?\}', block)]


@pytest.fixture
def api(isolated_brain):
    from app.main import app
    return TestClient(app, headers={"X-AO-Client": "office", "Origin": "http://localhost:4520"})


def test_the_seed_holds_exactly_the_17_approved_seats_in_order():
    assert [a["id"] for a in seed()["agents"]] == EXPECTED_SEATS


def test_the_api_roster_returns_all_17_seats_not_only_leads(api):
    got = api.get("/api/agents").json()["agents"]
    assert [a["id"] for a in got] == EXPECTED_SEATS
    assert sum(1 for a in got if not a["lead"]) == 9 and sum(1 for a in got if a["lead"]) == 8


def test_the_generated_ui_file_is_not_stale():
    ui = generated_ui_seats()
    assert [s["id"] for s in ui] == EXPECTED_SEATS
    by_id = {a["id"]: a for a in seed()["agents"]}
    assert all(s["dept"] == by_id[s["id"]]["dept"] and s["lead"] == bool(by_id[s["id"]].get("lead")) for s in ui)


def test_no_seat_id_appears_twice_in_any_source(api):
    for ids in ([a["id"] for a in seed()["agents"]],
                [a["id"] for a in api.get("/api/agents").json()["agents"]],
                [s["id"] for s in generated_ui_seats()],
                [a.id for a in defaults()]):
        assert [i for i, n in Counter(ids).items() if n > 1] == []


def test_every_department_has_exactly_one_lead_and_no_seat_has_an_unknown_department():
    leads = Counter(a.department for a in defaults() if a.lead)
    assert set(DEPTS) == EXPECTED_DEPTS
    assert {a.department for a in defaults()} == EXPECTED_DEPTS
    assert leads == {d: 1 for d in EXPECTED_DEPTS}


def test_live_departments_are_real_departments_and_every_stage_lead_is_that_departments_lead():
    pipe = config_mod.DEFAULTS["pipeline"]
    assert set(pipe["live_departments"]) <= set(DEPTS)
    lead_of = {a.department: a.id for a in defaults() if a.lead}
    for s in config_mod.DEFAULT_STAGES:
        assert s["dept"] in pipe["live_departments"], s
        assert s["lead"] == lead_of[s["dept"]], s


def test_the_two_exposure_keys_are_lead_seats_of_live_departments():
    keys = config_mod.DEFAULTS["exposure"]["keys"]
    by_id = {a.id: a for a in defaults()}
    live = set(config_mod.DEFAULTS["pipeline"]["live_departments"])
    for role in keys.values():
        assert by_id[role].lead and by_id[role].department in live


def test_every_seat_has_a_name_a_role_and_what_it_does():
    for a in load_roster()["agents"]:
        assert a.name and a.role and a.does, a.id


@pytest.mark.xfail(strict=True, reason="Part G finding: all 17 seats have empty boundaries; the persona catalog (row 19 follow-up) "
                                       "fills them. When it does, this XPASSes and the marker must be removed.")
def test_every_seat_has_boundaries():
    assert all(a.boundaries for a in load_roster()["agents"])


def test_loading_the_roster_twice_gives_the_same_seats_and_writes_nothing(tmp_path):
    files = [roster_mod.FILE, roster_mod.LOCAL]
    stamps = {p: (p.stat().st_mtime_ns, p.stat().st_size) for p in files if p.exists()}
    one, two = load_roster(tmp_path), load_roster(tmp_path)
    assert [dataclasses.asdict(a) for a in one["agents"]] == [dataclasses.asdict(a) for a in two["agents"]]
    assert list(tmp_path.rglob("*")) == []  # nothing written into the brain
    assert stamps == {p: (p.stat().st_mtime_ns, p.stat().st_size) for p in files if p.exists()}
