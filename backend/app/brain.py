"""Lightweight port of the context-retrieval parts of serve.mjs (vaultIndex/businessContext/
relevantNotes/contextText) plus a minimal stand-in for graph-build.mjs's /api/brain payload.

The full wiki-style graph layout (node positions, link bundling) in graph-build.mjs is a
visual-only concern for the brain-map screen; it is NOT in the execution path of run()/chat()
and is deferred. What run()/chat() actually need — note text for grounding — is implemented
here in full.
"""
from __future__ import annotations

import re
import time
from pathlib import Path

from . import db

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


# ---------- search: Postgres full text over note chunks, keyword scoring as the fallback ----------

CHUNK_CHARS = 900
_index_sig: dict = {"sig": None}


def chunk_note(name: str, body: str, folder: str = "") -> list[dict]:
    """Split a note on blank lines into chunks of about CHUNK_CHARS."""
    out, cur = [], ""
    for para in re.split(r"\n\s*\n", body):
        if cur and len(cur) + len(para) > CHUNK_CHARS:
            out.append(cur.strip())
            cur = ""
        cur += para + "\n\n"
    if cur.strip():
        out.append(cur.strip())
    return [{"note": name, "idx": i, "folder": folder, "body": c[: CHUNK_CHARS * 2]} for i, c in enumerate(out)]


def _signature(brain_path: Path) -> tuple:
    files = [p for p in brain_path.rglob("*") if p.is_file() and p.suffix.lower() in NOTE_EXT] if brain_path.exists() else []
    return (str(brain_path), len(files), max((p.stat().st_mtime for p in files), default=0))


async def reindex(brain_path: Path, force: bool = False) -> int:
    """Rebuild the search index when any note changed. Returns the number of chunks written (0 = unchanged)."""
    sig = _signature(brain_path)
    if not force and _index_sig["sig"] == sig:
        return 0
    chunks: list[dict] = []
    for name, body in vault_index(brain_path).items():
        chunks.extend(chunk_note(name, body))
    n = await db.brain_replace(chunks)
    _index_sig["sig"] = sig
    return n


_STOP = {"the", "and", "for", "with", "that", "this", "from", "are", "was", "not", "but", "you", "your", "our",
         "has", "have", "will", "can", "all", "any", "its", "into", "than", "then", "them", "they", "what", "when"}


def _words(text: str) -> list[str]:
    seen: list[str] = []
    for w in re.findall(r"[a-z0-9]{3,}", text.lower()):
        if w not in seen and w not in _STOP:
            seen.append(w)
    return seen


async def search(brain_path: Path, query: str, k: int = 4, dept: str = "") -> list[dict]:
    """Best chunks for a query: [{note, body}]. Never raises: on any index problem it falls back
    to the keyword scorer over the files, so an agent is never left without context."""
    try:
        await reindex(brain_path)
        hits = await db.brain_search(_words(query), k=k * 3)
        if dept:  # a note whose name mentions the department ranks first
            hits.sort(key=lambda h: 0 if re.search(dept, h["note"], re.IGNORECASE) else 1)
        seen, out = set(), []
        for h in hits:
            if h["note"] in seen:
                continue
            seen.add(h["note"])
            out.append({"note": h["note"], "body": h["body"]})
            if len(out) >= k:
                break
        if out:
            return out
    except Exception:
        _index_sig["sig"] = None
    idx = vault_index(brain_path)
    return [{"note": n, "body": idx[n][:800]} for n in relevant_notes(idx, dept or "zzzz", query, k)]


def brain_summary(brain_path: Path) -> dict:
    """Minimal /api/brain payload: note count + flat name list, no layout."""
    idx = vault_index(brain_path)
    return {"notes": len(idx), "names": sorted(idx.keys())}


# ---------- /api/brain: the note graph for the Brain view (port of graph-build.mjs) ----------

_LINK = re.compile(r"\[\[([^\]|#]+)")
_SKIP = {"node_modules", "99-Archive", ".obsidian", ".trash", ".git"}
_graph_cache: dict = {"sig": None, "graph": None}


def _read_vault(root: Path) -> tuple[dict[str, str], list[tuple[str, str]]]:
    """name -> group (top-level folder) and raw [[wiki links]] for every .md note."""
    groups: dict[str, str] = {}
    raw: list[tuple[str, str]] = []
    if not root.exists():
        return groups, raw
    for p in sorted(root.rglob("*.md")):
        rel = p.relative_to(root).parts
        if any(part in _SKIP or part.startswith(".") for part in rel):
            continue
        name = p.stem
        groups[name] = rel[0] if len(rel) > 1 else "00-Meta"
        try:
            text = p.read_text(errors="ignore")
        except OSError:
            continue
        for m in _LINK.finditer(text):
            raw.append((name, m.group(1).strip().split("/")[-1]))
    return groups, raw


def _layout(n: int, links: list[list[int]], deg: list[int], iters: int = 260) -> tuple[list[float], list[float]]:
    """Deterministic Fruchterman-Reingold pass (same recipe as graph-build.mjs's fallback)."""
    import math
    x = [0.0] * n
    y = [0.0] * n
    for i in range(n):
        a = i * 2.399963
        r = 0.3 + 0.7 * math.sqrt(i / max(n, 1))
        x[i], y[i] = math.cos(a) * r * 60, math.sin(a) * r * 60
    k = 7.0
    for it in range(iters):
        temp = 6 * (1 - it / iters) + 0.3
        vx = [0.0] * n
        vy = [0.0] * n
        for i in range(n):
            xi, yi = x[i], y[i]
            for j in range(i + 1, n):
                dx, dy = xi - x[j], yi - y[j]
                f = (k * k) / (dx * dx + dy * dy + 0.01)
                vx[i] += dx * f; vy[i] += dy * f; vx[j] -= dx * f; vy[j] -= dy * f
        for i, j in links:
            dx, dy = x[i] - x[j], y[i] - y[j]
            d = math.hypot(dx, dy) + 0.01
            f = d / k * 0.9
            vx[i] -= dx / d * f; vy[i] -= dy / d * f; vx[j] += dx / d * f; vy[j] += dy / d * f
        for i in range(n):
            g = 0.006 + 0.012 * min(1.0, deg[i] / 40)
            vx[i] -= x[i] * g
            vy[i] -= y[i] * g
            v = math.hypot(vx[i], vy[i]) or 1.0
            s = min(v, temp) / v
            x[i] += vx[i] * s
            y[i] += vy[i] * s
    return x, y


def brain_graph(brain_path: Path, max_nodes: int = 160) -> dict:
    """{notes, names, nodes:[{id,g,d,x,y}], links:[[i,j]], floor:[[x,y]]} — the shape
    src/braingraph.js exports, so the Brain view shows the live vault. Cached until a
    note changes; the most linked `max_nodes` notes are laid out."""
    import math
    files = [p for p in brain_path.rglob("*.md")] if brain_path.exists() else []
    sig = (len(files), max((p.stat().st_mtime for p in files), default=0))
    if _graph_cache["sig"] == sig and _graph_cache["graph"] is not None:
        return _graph_cache["graph"]
    groups, raw = _read_vault(brain_path)
    deg: dict[str, int] = {}
    seen: set[tuple[str, str]] = set()
    pairs: list[tuple[str, str]] = []
    for a, b in raw:
        if a not in groups or b not in groups or a == b:
            continue
        key = (a, b) if a < b else (b, a)
        if key in seen:
            continue
        seen.add(key)
        pairs.append(key)
        deg[a] = deg.get(a, 0) + 1
        deg[b] = deg.get(b, 0) + 1
    ids = sorted((n for n in groups if deg.get(n)), key=lambda n: (-deg[n], n))[:max_nodes]
    idx = {n: i for i, n in enumerate(ids)}
    links = [[idx[a], idx[b]] for a, b in pairs if a in idx and b in idx]
    x, y = _layout(len(ids), links, [deg[n] for n in ids])
    r = max((math.hypot(x[i], y[i]) for i in range(len(ids))), default=1.0) or 1.0
    nodes = [{"id": n, "g": groups[n], "d": deg[n], "x": round(x[i] / r, 3), "y": round(y[i] / r, 3)} for i, n in enumerate(ids)]
    floor = [[nd["x"], nd["y"]] for nd in nodes[:90]]
    graph = {"notes": len(groups), "names": sorted(groups), "nodes": nodes, "links": links, "floor": floor}
    _graph_cache.update(sig=sig, graph=graph)
    return graph
