"""Port of skills.mjs — a skill is how the owner wants one kind of work done.

  skills/<name>/SKILL.md                      shipped with the repo (examples)
  <brain>/Agents Office/skills/<name>/SKILL.md yours — wins on the same name
  skills/<name>.md                             a one-file skill is also fine

Agents have no file tools, so every readable file beside SKILL.md is inlined into the
prompt (capped — see LIMITS); binaries are listed by name only.
"""
from __future__ import annotations

import os
import re
from dataclasses import dataclass, field
from pathlib import Path

from .config import ROOT
from .roster import DEPTS

DEPT_KEYS = list(DEPTS.keys())

SHIPPED = ROOT / "skills"


def brain_dir(brain_path: Path) -> Path:
    return brain_path / "Agents Office" / "skills"


LIMITS = {"body": 6000, "files": 8000, "perFile": 4000}
TEXT_RE = re.compile(r"\.(md|txt|csv|json|ya?ml|html?|xml|tsv)$", re.IGNORECASE)
FRONT_MATTER_RE = re.compile(r"^﻿?---\r?\n([\s\S]*?)\r?\n---\r?\n?")
KV_RE = re.compile(r"^([A-Za-z_][\w-]*):\s*(.*)$")


def parse_skill(text: str) -> dict:
    meta: dict = {}
    body = text
    m = FRONT_MATTER_RE.match(text)
    if m:
        body = text[m.end():]
        key = None
        for line in m.group(1).splitlines():
            kv = KV_RE.match(line)
            if kv:
                key = kv.group(1).lower()
                v = kv.group(2).strip()
                if v.startswith("["):
                    meta[key] = [s.strip().strip("\"'") for s in v.strip("[]").split(",") if s.strip()]
                elif v == "":
                    meta[key] = []
                else:
                    meta[key] = v.strip("\"'")
            elif key and re.match(r"^\s*-\s+", line):
                if not isinstance(meta.get(key), list):
                    meta[key] = []
                meta[key].append(re.sub(r"^\s*-\s+", "", line).strip().strip("\"'"))
    return {"meta": meta, "body": body.strip()}


@dataclass
class Skill:
    name: str
    description: str
    agents: list[str]
    departments: list[str]
    everyone: bool
    text: str
    files: list[dict]
    path: str
    source: str


def _list(v) -> list[str]:
    if v is None:
        return []
    if isinstance(v, list):
        return v
    return [s.strip() for s in str(v).split(",") if s.strip()]


def _read_one(where: Path, entry: os.DirEntry, agents: list, problems: list[str]) -> Skill | None:
    p = where / entry.name
    dir_: Path | None = None
    if entry.is_dir():
        file = p / "SKILL.md"
        dir_ = p
        if not file.exists():
            problems.append(f"{entry.name}/: no SKILL.md — skipped")
            return None
    elif entry.name.lower().endswith(".md") and entry.name.upper() != "README.MD":
        file = p
    else:
        return None

    parsed = parse_skill(file.read_text())
    meta, body = parsed["meta"], parsed["body"]
    name = str(meta.get("name") or (entry.name if dir_ else re.sub(r"\.md$", "", entry.name, flags=re.IGNORECASE)))
    name = re.sub(r"[^a-z0-9._-]+", "-", name.strip().lower())
    label = f"{entry.name}/SKILL.md" if dir_ else entry.name
    if not body:
        problems.append(f"{label}: empty — skipped")
        return None

    ids = {a.id for a in agents}
    bound = []
    for s in _list(meta.get("agents")):
        sid = s.lower()
        if sid in ids:
            bound.append(sid)
        else:
            problems.append(f'{label}: "{sid}" is not an agent id — ignored (ids are in office.agents.json)')

    depts = []
    for s in _list(meta.get("departments")):
        k = s.lower()
        if k in DEPT_KEYS:
            depts.append(k)
        else:
            problems.append(f'{label}: "{k}" is not a department — ignored ({", ".join(DEPT_KEYS)})')

    for k in meta.keys():
        if k not in ("name", "description", "agents", "departments"):
            problems.append(f'{label}: unknown field "{k}" — ignored')

    if (_list(meta.get("agents")) or _list(meta.get("departments"))) and not bound and not depts:
        problems.append(f"{label}: none of its agents or departments exist — skipped (a skill with no valid binding would go to all 33)")
        return None

    text = body
    if len(body) > LIMITS["body"]:
        text = body[: LIMITS["body"]] + "\n[… trimmed]"
        problems.append(f'{label}: over {LIMITS["body"]} characters — trimmed; move detail into files beside it')

    files: list[dict] = []
    if dir_:
        used = 0
        for f in sorted(os.listdir(dir_)):
            if f == "SKILL.md" or f.startswith("."):
                continue
            fp = dir_ / f
            if not fp.is_file():
                continue
            if not TEXT_RE.search(f):
                files.append({"name": f, "text": None})
                continue
            t = fp.read_text().strip()
            if used >= LIMITS["files"]:
                files.append({"name": f, "text": None})
                problems.append(f'{entry.name}/{f}: skill files over {LIMITS["files"]} characters — listed by name only')
                continue
            if len(t) > LIMITS["perFile"]:
                t = t[: LIMITS["perFile"]] + "\n[… trimmed]"
                problems.append(f'{entry.name}/{f}: over {LIMITS["perFile"]} characters — trimmed')
            used += len(t)
            files.append({"name": f, "text": t})

    everyone = not bound and not depts
    return Skill(
        name=name,
        description=str(meta.get("description") or "").strip()[:160],
        agents=bound,
        departments=depts,
        everyone=everyone,
        text=text,
        files=files,
        path=str(file.relative_to(ROOT)),
        source="shipped" if where == SHIPPED else "brain",
    )


class Skills:
    def __init__(self, skills: list[Skill], problems: list[str]):
        self.skills = skills
        self.problems = problems

    def for_agent(self, a) -> list[Skill]:
        return [s for s in self.skills if s.everyone or a.id in s.agents or a.department in s.departments]

    def names(self, a) -> list[str]:
        return [s.name for s in self.for_agent(a)]

    def prompt_text(self, a) -> str:
        mine = self.for_agent(a)
        if not mine:
            return ""
        header = ('SKILLS — how the owner wants this kind of work done. When a task matches a skill, '
                  'follow it exactly: its steps, its format, its wording rules. Say which skill you '
                  'followed in one line at the end ("Skill: proposal").\n\n')
        parts = []
        for s in mine:
            head = f"### {s.name}" + (f" — {s.description}" if s.description else "")
            chunk = f"{head}\n{s.text}"
            for f in s.files:
                chunk += f"\n\n(attached file: {f['name']} — not readable here)" if f["text"] is None else f"\n\n--- {f['name']} ---\n{f['text']}"
            parts.append(chunk)
        return header + "\n\n".join(parts)

    def summary(self) -> dict:
        return {
            "count": len(self.skills),
            "shipped": sum(1 for s in self.skills if s.source == "shipped"),
            "brain": sum(1 for s in self.skills if s.source == "brain"),
            "problems": self.problems,
            "skills": [
                {"name": s.name, "description": s.description, "agents": s.agents, "departments": s.departments,
                 "everyone": s.everyone, "files": [f["name"] for f in s.files], "source": s.source, "path": s.path}
                for s in self.skills
            ],
        }


def load_skills(brain_path: Path, agents: list) -> Skills:
    problems: list[str] = []
    by_name: dict[str, Skill] = {}
    for where in (SHIPPED, brain_dir(brain_path)):
        if not where.exists():
            continue
        try:
            entries = list(os.scandir(where))
        except OSError:
            continue
        for e in entries:
            if e.name.startswith("."):
                continue
            s = _read_one(where, e, agents, problems)
            if s:
                if s.name in by_name and by_name[s.name].source == s.source:
                    loc = "skills/" if s.source == "shipped" else "the brain"
                    problems.append(f'"{s.name}" appears twice in {loc} — the later one wins')
                by_name[s.name] = s
    return Skills(list(by_name.values()), problems)
