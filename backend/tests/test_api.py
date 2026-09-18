"""Phase 1 API integration tests"""

import pytest
from fastapi.testclient import TestClient

from backend.main import app


@pytest.fixture
def client():
    """Create test client"""
    return TestClient(app)


def test_health_endpoint(client):
    """GET /api/health returns status"""
    response = client.get("/api/health")
    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "ok"
    assert data["version"] == "3.6.0-py"
    assert data["backend"] == "fastapi"
    assert "agents" in data
    assert "notes" in data


def test_agents_list(client):
    """GET /api/agents returns agent roster"""
    response = client.get("/api/agents")
    assert response.status_code == 200
    data = response.json()
    assert "agents" in data
    assert "count" in data
    assert "customized" in data
    assert "briefed" in data


def test_brain_notes(client):
    """GET /api/brain/notes returns brain vault"""
    response = client.get("/api/brain/notes")
    assert response.status_code == 200
    data = response.json()
    assert "notes" in data
    assert "total" in data
    assert isinstance(data["notes"], list)


def test_routines_list(client):
    """GET /api/routines returns routines (placeholder)"""
    response = client.get("/api/routines")
    assert response.status_code == 200
    data = response.json()
    assert isinstance(data, list)


def test_skills_list(client):
    """GET /api/skills returns skills (placeholder)"""
    response = client.get("/api/skills")
    assert response.status_code == 200
    data = response.json()
    assert isinstance(data, list)
