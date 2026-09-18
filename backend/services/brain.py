"""Brain vault loader (adapts graph-build.mjs)

Reads .md files from brain folder, parses [[wiki-links]], ranks by relevance.
"""

import re
from pathlib import Path
from typing import Dict, List, Tuple

from backend.config import get_config

SKIP_DIRS = {
    "node_modules",
    "99-Archive",
    ".obsidian",
    ".trash",
    ".git",
    "graphify-out",
    "command-centre-v2",
    "your-brain",
    "starter-vault",
    "pro-vault",
    "replit-handover",
    "Agents Office",
}


def read_vault(vault_path: Path) -> Tuple[Dict[str, Dict], List[Tuple[str, str]]]:
    """
    Read vault: return (notes, raw_links)

    notes: {name → {group, path, text}}
    raw_links: [(source_name, target_name), ...]
    """

    notes = {}
    raw_links = []

    if not vault_path.exists():
        return notes, raw_links

    def walk(dir_path: Path, top_group: str = ""):
        """Walk directory recursively"""
        if not dir_path.is_dir():
            return

        try:
            entries = dir_path.iterdir()
        except (PermissionError, OSError):
            return

        for entry in entries:
            # Skip
            if entry.name.startswith(".") or entry.name in SKIP_DIRS:
                continue

            if entry.is_dir():
                walk(entry, top_group or entry.name)
                continue

            if not entry.suffix == ".md":
                continue

            name = entry.stem
            try:
                text = entry.read_text(encoding="utf-8")
            except (UnicodeDecodeError, OSError):
                continue

            group = top_group or "00-Meta"
            notes[name] = {
                "group": group,
                "path": str(entry),
                "text": text,
                "hash": hash(text),
            }

            # Extract wiki links [[name]]
            for match in re.finditer(r"\[\[([^\]|#]+)", text):
                target = match.group(1).strip().split("/")[-1]
                raw_links.append((name, target))

    walk(vault_path)
    return notes, raw_links


def read_office_notes(vault_path: Path) -> List[Dict]:
    """Read notes written by agents: <vault>/Agents Office/*.md"""

    notes_dir = vault_path / "Agents Office"
    notes = []

    if not notes_dir.exists():
        return notes

    for file_path in notes_dir.glob("*.md"):
        try:
            text = file_path.read_text(encoding="utf-8")
            notes.append({"name": file_path.stem, "path": str(file_path), "text": text})
        except (UnicodeDecodeError, OSError):
            continue

    return notes


def rank_by_relevance(notes: List[Dict], query: str, top_k: int = 10) -> List[Dict]:
    """Rank notes by keyword relevance to query (simple TF-matching)"""

    query_words = set(query.lower().split())
    scored = []

    for note in notes:
        content = note.get("text", "").lower()
        title = note.get("name", "").lower()

        # Score: title matches weighted 2x
        title_matches = len(query_words & set(title.split()))
        content_matches = len(query_words & set(content.split()))
        score = (title_matches * 2) + content_matches

        if score > 0:
            scored.append((score, note))

    # Sort by score descending
    scored.sort(key=lambda x: x[0], reverse=True)

    return [note for _, note in scored[:top_k]]


def load_brain(brain_path: Path = None) -> Dict[str, any]:
    """Load complete brain state"""

    config = get_config()
    if brain_path is None:
        brain_path = config["brain_path"]

    # Read vault
    all_notes, raw_links = read_vault(brain_path)

    # Add agent notes
    office_notes = read_office_notes(brain_path)
    for note in office_notes:
        all_notes[note["name"]] = {
            "group": "Agents Office",
            "path": note["path"],
            "text": note["text"],
        }
        # Extract links from agent notes
        for match in re.finditer(r"\[\[([^\]|#]+)", note["text"]):
            target = match.group(1).strip().split("/")[-1]
            raw_links.append((note["name"], target))

    return {
        "all_notes": list(all_notes.values()),
        "notes_by_name": all_notes,
        "raw_links": raw_links,
        "vault_path": str(brain_path),
    }


# Singleton cache
_brain_cache = None


def get_brain(refresh: bool = False) -> Dict:
    """Get cached brain, optionally refresh"""
    global _brain_cache
    if _brain_cache is None or refresh:
        _brain_cache = load_brain()
    return _brain_cache
