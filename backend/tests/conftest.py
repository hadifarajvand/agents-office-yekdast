import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
sys.path.insert(0, str(Path(__file__).resolve().parent))

from fakes import FakeDB  # noqa: E402

# Headers the office page sends on every state-changing request (see main.guard).
OFFICE_HEADERS = {"X-AO-Client": "office"}


@pytest.fixture
def fake_db(monkeypatch):
    return FakeDB().install(monkeypatch)


@pytest.fixture
def isolated_brain(monkeypatch, tmp_path):
    """Point the app at a throwaway brain so tests never write into ./brain."""
    from app import main
    monkeypatch.setattr(main.cfg, "brain_path", tmp_path)
    return tmp_path
