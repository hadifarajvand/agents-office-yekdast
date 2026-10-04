"""Brain write governance. Agents never edit the brain's notes. They propose a note; the
owner approves or rejects it; an approved note is written under `Agents Office/notes/` and never
over an existing file. Curated notes (the vault, playbooks, skills) are therefore changed by people only."""
from __future__ import annotations

import json
import re
import time
import uuid
from pathlib import Path

from .config import load_config

MAX_TITLE, MAX_BODY = 120, 20000


class ProposalError(Exception):
    pass


def _dir(brain_path: Path | None = None) -> Path:
    return (brain_path or load_config().brain_path) / "Agents Office" / "proposals"


def _notes_dir(brain_path: Path | None = None) -> Path:
    return (brain_path or load_config().brain_path) / "Agents Office" / "notes"


def _slug(title: str) -> str:
    return re.sub(r"[^a-z0-9]+", "-", title.lower()).strip("-")[:60] or "note"


def propose(seat_id: str, title: str, body: str, *, job_id: str = "", brain_path: Path | None = None) -> dict:
    title, body = str(title or "").strip(), str(body or "").strip()
    if not title or not body:
        raise ProposalError("a note needs a title and a body")
    if len(title) > MAX_TITLE or len(body) > MAX_BODY:
        raise ProposalError(f"title is limited to {MAX_TITLE} characters and body to {MAX_BODY}")
    d = _dir(brain_path)
    d.mkdir(parents=True, exist_ok=True)
    pid = uuid.uuid4().hex[:10]
    rec = {"id": pid, "seat": seat_id, "title": title, "body": body, "job_id": job_id,
           "status": "pending", "at": time.time()}
    (d / f"{pid}.json").write_text(json.dumps(rec, indent=1))
    return rec


def list_proposals(status: str = "", brain_path: Path | None = None) -> list[dict]:
    d = _dir(brain_path)
    out = []
    for f in sorted(d.glob("*.json")) if d.exists() else []:
        try:
            r = json.loads(f.read_text())
        except json.JSONDecodeError:
            continue
        if not status or r.get("status") == status:
            out.append(r)
    return sorted(out, key=lambda r: r.get("at", 0))


def decide(pid: str, verdict: str, brain_path: Path | None = None) -> dict:
    if not re.fullmatch(r"[0-9a-f]{10}", pid or ""):
        raise ProposalError("unknown proposal")
    f = _dir(brain_path) / f"{pid}.json"
    if not f.exists():
        raise ProposalError("unknown proposal")
    rec = json.loads(f.read_text())
    if rec["status"] != "pending":
        raise ProposalError(f'already {rec["status"]}')
    if verdict not in ("approve", "reject"):
        raise ProposalError('verdict must be "approve" or "reject"')
    rec["status"] = "approved" if verdict == "approve" else "rejected"
    if verdict == "approve":
        nd = _notes_dir(brain_path)
        nd.mkdir(parents=True, exist_ok=True)
        target = nd / f"{_slug(rec['title'])}.md"
        n = 2
        while target.exists():  # never overwrite
            target = nd / f"{_slug(rec['title'])}-{n}.md"
            n += 1
        target.write_text(f"# {rec['title']}\n\n_proposed by {rec['seat']}, approved by the owner_\n\n{rec['body']}\n")
        rec["path"] = str(target.name)
    rec["decided_at"] = time.time()
    f.write_text(json.dumps(rec, indent=1))
    return rec
