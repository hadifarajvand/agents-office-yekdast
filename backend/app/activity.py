"""Live activity: every real call the office makes (stage moves, model calls, containers,
notifications, brain access) becomes one event in a ring buffer. The UI polls
GET /api/activity?since=<seq> and plays each event as its effect, so nothing on screen
moves unless the backend did something."""
from __future__ import annotations

import re
import time
from collections import deque

_buf: deque[dict] = deque(maxlen=400)
_seq = 0
_sink = None  # set in the queue worker: forwards each event to the API process (see jobqueue)

# stack connectors the UI draws as tiles (key -> display name, departments they sit in)
STACK = {
    "router": ("9router", ["exec", "engineering"]),
    "postgres": ("Postgres", ["exec", "engineering", "devops"]),
    "docker": ("Docker sandbox", ["engineering", "devops"]),
    "egress": ("Egress proxy", ["engineering", "secdata"]),
    "telegram": ("Telegram", ["exec"]),
    "dokploy": ("Dokploy", ["devops"]),
    "brain": ("Brain", ["exec", "engineering", "revenue", "devops", "secdata", "fin", "content", "frontend"]),
}


def _lead_of(stage: str | None) -> str | None:
    if not stage:
        return None
    try:
        from .config import load_config
        for s in load_config().pipeline["stages"]:
            if s["name"] == stage:
                return s.get("lead")
    except Exception:
        pass
    return None


def emit(kind: str, text: str, *, agent: str | None = None, connector: str | None = None,
         job: str | None = None, stage: str | None = None, level: str = "info") -> None:
    """Never raises: logging an effect must not break the work."""
    global _seq
    try:
        _seq += 1
        ev = {"seq": _seq, "at": int(time.time() * 1000), "kind": kind, "text": str(text)[:200],
              "agent": agent or _lead_of(stage), "connector": connector, "job": job,
              "stage": stage, "level": level}
        _buf.append(ev)
        if _sink is not None:
            _sink(ev)
    except Exception:
        pass


def ingest(ev: dict) -> None:
    """An event that happened in another process (the queue worker): same buffer, this process's seq."""
    global _seq
    _seq += 1
    _buf.append({**ev, "seq": _seq})


def label_parts(label: str) -> tuple[str | None, str | None]:
    """'job:<id>:<stage>' -> (id, stage)"""
    m = re.match(r"^job:([^:]+):([^:]+)", label or "")
    return (m.group(1), m.group(2)) if m else (None, None)


def since(seq: int = 0) -> dict:
    return {"seq": _seq, "events": [e for e in _buf if e["seq"] > seq]}
