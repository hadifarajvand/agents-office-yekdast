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
