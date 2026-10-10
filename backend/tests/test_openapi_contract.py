"""The HTTP surface is pinned: every route (method + path) is listed in tests/api_routes.txt, so a
route cannot appear, vanish or be renamed without the diff showing in review. The schema is served
at /api/openapi.json to a loopback client only. Regenerate the list on purpose with
`UPDATE_API_ROUTES=1 pytest tests/test_openapi_contract.py`."""
from __future__ import annotations

import os
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from app.main import app

SNAPSHOT = Path(__file__).with_name("api_routes.txt")
VERBS = {"get", "post", "put", "patch", "delete"}


def routes_now() -> list[str]:
    spec = app.openapi()
    return sorted(f"{verb.upper()} {path}" for path, ops in spec["paths"].items() for verb in ops if verb in VERBS)


def test_route_list_matches_the_pinned_snapshot():
    now = routes_now()
    if os.environ.get("UPDATE_API_ROUTES") == "1":
        SNAPSHOT.write_text("\n".join(now) + "\n", encoding="utf-8")
    pinned = SNAPSHOT.read_text(encoding="utf-8").split()
    pinned = [f"{pinned[i]} {pinned[i + 1]}" for i in range(0, len(pinned), 2)]
    added, gone = sorted(set(now) - set(pinned)), sorted(set(pinned) - set(now))
    assert not added and not gone, f"HTTP surface changed. added: {added} removed: {gone}. If intended: UPDATE_API_ROUTES=1"


def test_promote_is_one_owner_route_and_nothing_else_names_it():
    promote = [r for r in routes_now() if "promote" in r]  # GET is the read-only status; POST is the owner's act
    assert promote == ["GET /api/jobs/{job_id}/promote", "POST /api/jobs/{job_id}/promote"], promote


def test_every_mutating_route_sits_under_api():
    bad = [r for r in routes_now() if not r.startswith("GET ") and " /api/" not in r]
    assert bad == [], bad


@pytest.fixture
def raw_client():
    # no lifespan: nothing here touches Postgres
    return TestClient(app, base_url="http://127.0.0.1")


def test_schema_is_served_to_a_loopback_client(raw_client, monkeypatch):
    import app.main as m
    monkeypatch.setattr(m, "LOOPBACK_CLIENTS", {"testclient"})  # starlette's TestClient reports this peer
    r = raw_client.get("/api/openapi.json")
    assert r.status_code == 200 and r.json()["info"]["title"] == "FastAPI"
    assert "/api/jobs/{job_id}/promote" in r.json()["paths"]


def test_schema_is_a_404_for_a_remote_client(raw_client):
    r = raw_client.get("/api/openapi.json")  # peer is "testclient", not loopback
    assert r.status_code == 404


def test_swagger_and_redoc_pages_stay_off(raw_client):
    assert raw_client.get("/docs").status_code == 404 and raw_client.get("/redoc").status_code == 404
