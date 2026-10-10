"""Port of roster.mjs — the roster (fixed seats from the seed, eight departments).

Precedence, later wins: built-in defaults <- office.agents.json <- <brain>/Agents Office/agents.json
<- office.agents.local.json (gitignored). Departments, leads and seats cannot change from these
files; the office ignores such edits and says so (see CLAUDE.md).
"""
from __future__ import annotations

import json
from dataclasses import dataclass, field
from pathlib import Path

from .config import ROOT, load_config
from .models import norm_model

FILE = ROOT / "office.agents.json"
LOCAL = ROOT / "office.agents.local.json"


def brain_file(brain_path: Path) -> Path:
    return brain_path / "Agents Office" / "agents.json"


EDITABLE = ["name", "role", "does", "tools", "brief", "model", "effort", "boundaries"]
BOUNDARIES_LIST_MAX = 20
BOUNDARIES_ITEM_MAX = 200
BRIEF_MAX = 2000
MODELS = ["sonnet", "opus", "fable", "haiku"]
EFFORTS = ["low", "medium", "high", "xhigh", "max"]

_SEED_PATH = Path(__file__).resolve().parent / "seed" / "roster_seed.json"
_SEED = json.loads(_SEED_PATH.read_text())
# "brain" is a non-department pseudo-key in src/data.js's DEPTS — not a real department,
# excluded here so this matches routines.mjs's DEPT_KEYS (exec/revenue/engineering/frontend/devops/secdata/fin/content).
DEPTS = {k: v for k, v in _SEED["depts"].items() if k != "brain"}


@dataclass
class Agent:
    id: str
    department: str
    lead: bool
    name: str
    role: str = ""
    does: str = ""
    tools: list[str] = field(default_factory=list)
    brief: str = ""
    model: str = ""
    effort: str = ""
    boundaries: dict = field(default_factory=dict)


def defaults() -> list[Agent]:
    v1_by_id = {v["id"]: v for v in _SEED["v1"]}
    out = []
    for a in _SEED["agents"]:
        p = v1_by_id.get(a["id"], {})
        out.append(Agent(
            id=a["id"], department=a["dept"], lead=bool(a["lead"]), name=a["name"],
            role=p.get("role", ""), does=p.get("tagline", ""), tools=[], brief="", model="", effort="",
        ))
    return out


def validate(doc, base: list[Agent] | None = None) -> dict:
    base = base or defaults()
    problems: list[str] = []
    if isinstance(doc, list):
        lst = doc
    elif isinstance(doc, dict) and isinstance(doc.get("agents"), list):
        lst = doc["agents"]
    else:
        return {"agents": base, "problems": ['the file must be {"agents": [...]}']}

    out = [Agent(**{**a.__dict__, "tools": list(a.tools), "boundaries": json.loads(json.dumps(a.boundaries))}) for a in base]
    by_id = {a.id: a for a in out}
    seen: set[str] = set()

    for e in lst:
        if not isinstance(e, dict) or not e.get("id"):
            problems.append('an entry has no "id" — skipped')
            continue
        eid = e["id"]
        a = by_id.get(eid)
        if not a:
            problems.append(f'"{eid}" is not one of the seats — skipped (new agents are not supported; rename a seat instead)')
            continue
        if eid in seen:
            problems.append(f'"{eid}" appears twice — the later entry wins')
        seen.add(eid)

        if "department" in e and e["department"] != a.department:
            problems.append(f'"{eid}": department cannot change ({a.department} → {e["department"]}) — ignored')
        if "lead" in e and bool(e["lead"]) != a.lead:
            problems.append(f'"{eid}": lead cannot change — ignored')
        for k in e.keys():
            if k not in ("id", "department", "lead", *EDITABLE):
                problems.append(f'"{eid}": unknown field "{k}" — ignored')

        if "name" in e:
            n = str(e["name"]).strip()
            if not n:
                problems.append(f'"{eid}": empty name — kept "{a.name}"')
            else:
                a.name = n[:32].upper()
        if "role" in e:
            a.role = str(e["role"]).strip()[:80]
        if "does" in e:
            a.does = str(e["does"]).strip()[:400]
        if "tools" in e:
            if not isinstance(e["tools"], list):
                problems.append(f'"{eid}": tools must be a list — ignored')
            else:
                a.tools = [s for s in (str(t).strip() for t in e["tools"]) if s][:12]
        if "model" in e:
            m = norm_model(str(e["model"] or ""))
            if not str(e["model"] or "").strip():
                a.model = ""
            elif m:
                a.model = m
            else:
                problems.append(f'"{eid}": model must be sonnet, opus, fable, haiku or a router id like oc/name (got "{e["model"]}") — kept {a.model or "the office default"}')
        if "effort" in e:
            v = str(e["effort"] or "").lower().strip()
            if not v:
                a.effort = ""
            elif v in EFFORTS:
                a.effort = v
            else:
                problems.append(f'"{eid}": effort must be low, medium, high, xhigh or max (got "{e["effort"]}") — kept {a.effort or "the default"}')
        if "brief" in e:
            raw = e["brief"]
            b = ("\n".join(str(x) for x in raw) if isinstance(raw, list) else str(raw)).strip()
            if len(b) > BRIEF_MAX:
                problems.append(f'"{eid}": brief is over {BRIEF_MAX} characters — trimmed (put the long version in a skill)')
            a.brief = b[:BRIEF_MAX]
        if "boundaries" in e:
            b = e["boundaries"]
            if not isinstance(b, dict):
                problems.append(f'"{eid}": boundaries must be an object — ignored')
            else:
                parsed: dict = {}
                for key in ("can", "cannot"):
                    v = b.get(key)
                    if v is None:
                        continue
                    if not isinstance(v, list):
                        problems.append(f'"{eid}": boundaries.{key} must be a list — ignored')
                        continue
                    parsed[key] = [str(x).strip()[:BOUNDARIES_ITEM_MAX] for x in v if str(x).strip()][:BOUNDARIES_LIST_MAX]
                esc = b.get("escalation")
                if esc is not None:
                    if not isinstance(esc, list):
                        problems.append(f'"{eid}": boundaries.escalation must be a list — ignored')
                    else:
                        parsed_esc = []
                        for item in esc[:BOUNDARIES_LIST_MAX]:
                            if not isinstance(item, dict) or not item.get("condition") or not item.get("target_agent"):
                                problems.append(f'"{eid}": boundaries.escalation entries need "condition" and "target_agent" — one skipped')
                                continue
                            parsed_esc.append({
                                "condition": str(item["condition"]).strip()[:BOUNDARIES_ITEM_MAX],
                                "target_agent": str(item["target_agent"]).strip(),
                            })
                        parsed["escalation"] = parsed_esc
                a.boundaries = parsed

    return {"agents": out, "problems": problems}


def boundaries_text(a: Agent) -> str:
    """Rendered the same way agent_brief() renders brief/skills: read freely
    before every task so the model carries its own CAN/CANNOT/ESCALATION
    contract, not just the office's tool-policy gate."""
    b = a.boundaries or {}
    parts = []
    if b.get("can"):
        parts.append("YOU CAN:\n" + "\n".join(f"- {x}" for x in b["can"]))
    if b.get("cannot"):
        parts.append("YOU CANNOT:\n" + "\n".join(f"- {x}" for x in b["cannot"]))
    if b.get("escalation"):
        parts.append("ESCALATE:\n" + "\n".join(f'- {x["condition"]} -> {x["target_agent"]}' for x in b["escalation"]))
    return "\n\n".join(parts)


def _read(p: Path):
    if not p.exists():
        return None
    try:
        return json.loads(p.read_text())
    except json.JSONDecodeError as e:
        return {"__error": str(e)}


def load_roster(brain_path: Path | None = None) -> dict:
    brain_path = brain_path or load_config().brain_path
    agents = defaults()
    problems: list[str] = []
    sources = [FILE, brain_file(brain_path), LOCAL]

    def label(p: Path) -> str:
        return p.name if p in (FILE, LOCAL) else "brain/Agents Office/agents.json"

    for p in sources:
        doc = _read(p)
        if doc is None:
            continue
        rel = label(p)
        if isinstance(doc, dict) and "__error" in doc:
            problems.append(f'{rel}: not valid JSON ({doc["__error"].splitlines()[0]}) — ignored')
            continue
        r = validate(doc, agents)
        agents = r["agents"]
        problems.extend(f'{rel}: {p_}' for p_ in r["problems"])

    base_defaults = defaults()
    customised = sum(
        1 for a, d in zip(agents, base_defaults)
        if a.name != d.name or a.role != d.role or a.does != d.does or a.brief
    )
    return {
        "agents": agents,
        "problems": problems,
        "customised": customised,
        "briefed": sum(1 for a in agents if a.brief),
        "files": [label(p) for p in sources if p.exists()],
    }


def dept_name(k: str) -> str:
    return DEPTS.get(k, k)
