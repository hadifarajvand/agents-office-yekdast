"""Lightweight port of the context-retrieval parts of serve.mjs (vaultIndex/businessContext/
relevantNotes/contextText) plus a minimal stand-in for graph-build.mjs's /api/brain payload.

The full wiki-style graph layout (node positions, link bundling) in graph-build.mjs is a
visual-only concern for the brain-map screen; it is NOT in the execution path of run()/chat()
and is deferred. What run()/chat() actually need — note text for grounding — is implemented
here in full.
"""
from __future__ import annotations

import re
from pathlib import Path

NOTE_EXT = {".md", ".txt"}


def _walk_notes(root: Path) -> dict[str, str]:
    out: dict[str, str] = {}
    if not root.exists():
        return out
    for p in root.rglob("*"):
        if p.is_file() and p.suffix.lower() in NOTE_EXT:
            try:
                out[p.stem] = p.read_text(errors="ignore")
            except Exception:
                continue
    return out


def vault_index(brain_path: Path) -> dict[str, str]:
    """name -> text, merging vault notes with live office notes (office notes win)."""
    idx = _walk_notes(brain_path)
    idx.update(_walk_notes(brain_path / "Agents Office"))
    return idx


def business_context(index: dict[str, str], limit: int = 1200) -> str:
    names = [n for n in index if re.search(r"business.model|voice|claude", n, re.IGNORECASE)]
    parts = [index[n][:limit] for n in names[:3]]
    return "\n\n".join(parts)


def relevant_notes(index: dict[str, str], dept: str, text: str, n: int = 4) -> list[str]:
    words = set(re.findall(r"[a-z0-9]{3,}", text.lower()))
    scored = []
    for name, body in index.items():
        hay = f"{name} {body[:500]}".lower()
        score = sum(1 for w in words if w in hay)
        if re.search(dept, name, re.IGNORECASE):
            score += 2
        if score > 0:
            scored.append((score, name))
    scored.sort(key=lambda x: -x[0])
    return [name for _, name in scored[:n]]


def context_text(index: dict[str, str], names: list[str], limit: int = 800) -> str:
    parts = [f"## {n}\n{index[n][:limit]}" for n in names if n in index]
    return "\n\n".join(parts)


def brain_summary(brain_path: Path) -> dict:
    """Minimal /api/brain payload: note count + flat name list, no layout."""
    idx = vault_index(brain_path)
    return {"notes": len(idx), "names": sorted(idx.keys())}
