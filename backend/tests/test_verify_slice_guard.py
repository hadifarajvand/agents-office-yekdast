"""scripts/verify_slice.py must not be able to touch the live stack (MASTER_PLAN Part G, S7).

The script submits real jobs, clicks the owner's gates and kills what is left. Before this slice it fetched a
token from BASE_URL at import time and ran against whatever answered there. Now it refuses unless the run is
explicitly allowed, the target is loopback, and the server itself reports a throwaway database. None of these
tests starts the script against a server: the network is stubbed to fail the test if it is touched.
"""
from __future__ import annotations

import importlib.util
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from app import db

SCRIPT = Path(__file__).resolve().parents[2] / "scripts" / "verify_slice.py"
FLAG = "--allow-test-database"


def load():
    spec = importlib.util.spec_from_file_location("verify_slice_under_test", SCRIPT)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


@pytest.fixture
def mod():
    return load()


@pytest.fixture
def no_network(monkeypatch, mod):
    """Any HTTP, token fetch, client or report write fails the test."""
    import urllib.request

    import httpx
    touched: list[str] = []

    def boom(name):
        def f(*a, **k):
            touched.append(name)
            raise AssertionError(f"{name} was called")
        return f
    monkeypatch.setattr(httpx, "get", boom("httpx.get"))
    monkeypatch.setattr(httpx, "Client", boom("httpx.Client"))
    monkeypatch.setattr(urllib.request, "urlopen", boom("urlopen"))
    monkeypatch.setattr(mod, "finish", boom("finish"))
    monkeypatch.delenv("BASE_URL", raising=False)
    monkeypatch.delenv("AO_RESTART_CMD", raising=False)
    return touched


# ---------- importing the script does nothing ----------
def test_importing_the_script_makes_no_network_call(monkeypatch):
    import urllib.request

    import httpx

    def boom(*a, **k):
        raise AssertionError("network touched at import")
    monkeypatch.setattr(urllib.request, "urlopen", boom)
    monkeypatch.setattr(httpx, "Client", boom)
    monkeypatch.setattr(httpx, "get", boom)
    monkeypatch.delenv("AO_API_TOKEN", raising=False)
    load()


# ---------- the guard, before any HTTP ----------
def test_without_the_flag_it_refuses(mod):
    why = mod.preflight("http://127.0.0.1:4597", allowed=False)
    assert why and FLAG in why


@pytest.mark.parametrize("base", ["http://example.com", "http://10.0.0.5:4520", "https://office.yekdast.com",
                                  "http://127.0.0.1.evil.com", "http://localhost@evil.com", "127.0.0.1:4520", ""])
def test_a_target_that_is_not_loopback_is_refused(mod, base):
    assert mod.preflight(base, allowed=True)


@pytest.mark.parametrize("base", ["http://127.0.0.1:4520", "http://localhost:4597", "http://[::1]:4520", "http://127.0.0.1:4597/"])
def test_loopback_with_the_flag_passes_the_preflight(mod, base):
    assert mod.preflight(base, allowed=True) is None


def test_restart_needs_its_own_command_never_the_live_restart_script(mod):
    assert mod.preflight("http://127.0.0.1:4597", allowed=True, with_restart=True, restart_cmd="")
    assert mod.preflight("http://127.0.0.1:4597", allowed=True, with_restart=True, restart_cmd="./restart-ui.sh") is None


# ---------- the guard, after the server says which database it uses ----------
@pytest.mark.parametrize("health", [{}, {"database": {}}, {"database": {"name": ""}}, {"database": None}, {"database": "office_ui"}, None])
def test_a_server_that_does_not_report_its_database_is_refused(mod, health):
    assert mod.check_database(health)


@pytest.mark.parametrize("name", ["office", "postgres", "office_ui_backup", "ui", "office_testing", "production"])
def test_a_real_database_name_is_refused(mod, name):
    why = mod.check_database({"database": {"name": name}})
    assert why and name in why


@pytest.mark.parametrize("name", ["office_ui", "office_test", "office_verify", "x_ui"])
def test_a_throwaway_database_name_is_accepted(mod, name):
    assert mod.check_database({"database": {"name": name}}) is None


# ---------- main(): refuses before it creates anything ----------
def test_main_refuses_without_the_flag_and_touches_nothing(mod, no_network):
    assert mod.main([]) == 2 and no_network == []


def test_main_refuses_a_remote_base_and_touches_nothing(mod, no_network, monkeypatch):
    monkeypatch.setenv("BASE_URL", "http://office.example.com")
    assert mod.main([FLAG]) == 2 and no_network == []


def test_main_refuses_restart_without_a_command_and_touches_nothing(mod, no_network):
    assert mod.main([FLAG, "--with-restart"]) == 2 and no_network == []


def test_main_refuses_the_live_database_before_connecting(mod, no_network, monkeypatch):
    calls: list = []
    monkeypatch.setattr(mod, "fetch_health", lambda base: {"database": {"name": "office"}})
    monkeypatch.setattr(mod, "connect", lambda base: calls.append(base))
    monkeypatch.setattr(mod, "run", lambda: calls.append("run") or 0)
    assert mod.main([FLAG]) == 2 and calls == [] and no_network == []


def test_main_refuses_when_the_server_cannot_be_reached(mod, no_network, monkeypatch):
    def down(base):
        raise ConnectionRefusedError("nothing there")
    monkeypatch.setattr(mod, "fetch_health", down)
    monkeypatch.setattr(mod, "connect", lambda base: pytest.fail("connected"))
    assert mod.main([FLAG]) == 2


def test_main_runs_against_a_throwaway_database(mod, no_network, monkeypatch):
    calls: list = []
    monkeypatch.setattr(mod, "fetch_health", lambda base: {"database": {"name": "office_ui"}})
    monkeypatch.setattr(mod, "connect", lambda base: calls.append(("connect", base)))
    monkeypatch.setattr(mod, "run", lambda: calls.append(("run",)) or 0)
    assert mod.main([FLAG, "--scripted"]) == 0
    assert calls == [("connect", "http://127.0.0.1:4520"), ("run",)] and mod.SCRIPTED is True
    assert mod.DB_NAME == "office_ui"


def test_connect_uses_the_token_from_the_environment_without_fetching_one(mod, no_network, monkeypatch):
    class Stub:
        def __init__(self, **kw):
            self.kw = kw
            self.event_hooks = {}
    monkeypatch.setattr(mod.httpx, "Client", Stub)
    monkeypatch.setenv("AO_API_TOKEN", "t0k3n")
    mod.connect("http://127.0.0.1:4597")
    assert mod.c.kw["headers"] == {"X-AO-Client": "office", "X-AO-Token": "t0k3n"}
    assert mod.c.kw["base_url"] == "http://127.0.0.1:4597"


# ---------- the database name the guard reads ----------
@pytest.mark.parametrize("url,name", [
    ("postgresql://office:pw@postgres:5432/office_ui", "office_ui"),
    ("postgresql+asyncpg://office:pw@127.0.0.1:5432/office_test?sslmode=disable", "office_test"),
    ("postgresql://office@localhost/office", "office"),
    ("", ""), ("not a url", ""), ("postgresql://office:pw@host:5432/", ""),
])
def test_database_name_is_only_the_name(url, name):
    assert db.database_name(url) == name


@pytest.fixture
def api(fake_db, isolated_brain):
    from app.main import app
    return TestClient(app, headers={"X-AO-Client": "office", "Origin": "http://localhost:4520"})


def test_health_reports_the_database_name_and_nothing_else_about_it(api, monkeypatch):
    monkeypatch.setattr(db, "DATABASE_URL", "postgresql://office:SECRET-PW@db.internal:5432/office_ui")
    r = api.get("/api/health")
    assert r.json()["database"] == {"name": "office_ui"}
    assert "SECRET-PW" not in r.text and "db.internal" not in r.text


# ---------- the script's expectations follow the real configuration ----------
def test_expected_roles_match_the_pipeline_rule_for_every_build_lane_stage(mod, api):
    from app.config import load_config
    from app.pipeline import exposure as exp
    cfg = load_config()
    pipeline = api.get("/api/health").json()["pipeline"]
    live = set(pipeline["liveDepartments"])
    stages = {s["name"]: s for s in pipeline["stages"]}
    for name in pipeline["lanes"]["build"]["stages"]:
        assert mod.expected_roles(stages[name], live) == set(exp.stage_roles(cfg, name)), name
    assert mod.OWNER_GATES == set(exp.owner_gates(cfg)) - {"research"}


def test_expected_owner_clicks_are_the_stages_where_only_the_owner_is_left(mod, api):
    pipeline = api.get("/api/health").json()["pipeline"]
    clicks = mod.expected_owner_clicks(pipeline)
    # exec, engineering, secdata and devops are live: the owner decides verify and handoff, nothing else.
    assert clicks == ["verify", "handoff"]


def test_offline_seat_sets_come_from_the_roster_not_a_hardcoded_list(mod, api):
    body = api.get("/api/health").json()
    leads, seats = mod.offline_ids(body["agents"], set(body["pipeline"]["liveDepartments"]))
    assert {"lexi", "alead", "elead", "mlead"} <= leads and "sec-compliance" not in leads and "devops-cd" not in leads
    assert {"piper", "cmail", "gfx"} <= seats and not (seats & leads)


def test_the_pinned_counts_match_the_running_roster_and_checklist(mod, api):
    from app.connectors.promote import checklist
    body = api.get("/api/health").json()
    assert (mod.SEATS, mod.DEPARTMENTS) == (len(body["agents"]), len({a["department"] for a in body["agents"]}))
    assert mod.CHECKLIST_ITEMS == len(checklist({}, []))
