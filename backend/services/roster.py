"""Agent roster loader (adapts roster.mjs)

Loads: office.agents.json → <brain>/Agents Office/agents.json → office.agents.local.json
Merges and validates. 35 seats fixed (6 depts × ~6 agents).
"""

import json
from pathlib import Path
from typing import Dict, List, Any, Tuple

from backend.config import get_config

# Load agent defaults from office.agents.json
def _load_defaults():
    """Load default agents from office.agents.json"""
    try:
        config = get_config()
        agents_file = config["brain_path"].parent / "office.agents.json"
        if agents_file.exists():
            data = json.loads(agents_file.read_text(encoding="utf-8"))
            if isinstance(data, dict) and "agents" in data:
                return data["agents"]
            elif isinstance(data, list):
                return data
    except Exception as e:
        # Debug: print why loading failed
        import sys
        print(f"Warning: Could not load agents from office.agents.json: {e}", file=sys.stderr)
    # Fallback: minimal set
    return [
        {
            "id": "alice",
            "department": "marketing",
            "lead": True,
            "name": "ALICE",
            "role": "Lead",
        },
        {
            "id": "bob",
            "department": "marketing",
            "lead": False,
            "name": "BOB",
            "role": "Agent",
        },
    ]

AGENTS_DEFAULTS = _load_defaults()

EDITABLE_FIELDS = {"name", "role", "does", "tools", "brief", "model", "effort"}
BRIEF_MAX = 2000
VALID_MODELS = {"sonnet", "opus", "fable", ""}
VALID_EFFORTS = {"low", "medium", "high", "xhigh", "max", ""}


def read_json(path: Path) -> Dict:
    """Safely read JSON"""
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (FileNotFoundError, json.JSONDecodeError):
        return {}


def validate_agents(
    doc: Dict | List, base: List[Dict] = None
) -> Tuple[List[Dict], List[str]]:
    """Validate agent document, return (agents, problems)"""

    if base is None:
        base = AGENTS_DEFAULTS

    problems = []

    # Extract agents list
    agents_list = None
    if isinstance(doc, list):
        agents_list = doc
    elif isinstance(doc, dict) and "agents" in doc:
        agents_list = doc["agents"]

    if agents_list is None:
        return base, ['File must be {"agents": [...]}']

    # Start with defaults
    output = [a.copy() for a in base]
    seen = set()

    for entry in agents_list:
        if not isinstance(entry, dict) or "id" not in entry:
            problems.append('Entry missing "id" — skipped')
            continue

        agent_id = entry["id"]
        agent = next((a for a in output if a["id"] == agent_id), None)

        if agent is None:
            problems.append(f'"{agent_id}" not in 35 seats — skipped')
            continue

        if agent_id in seen:
            problems.append(f'"{agent_id}" appears twice — later wins')
        seen.add(agent_id)

        # Validate editable fields
        for key in entry:
            if key not in {"id", "department", "lead", *EDITABLE_FIELDS}:
                problems.append(f'"{agent_id}": unknown field "{key}" — ignored')

        # Cannot change these
        if entry.get("department") != agent["department"]:
            problems.append(f'"{agent_id}": department cannot change — ignored')
        if entry.get("lead") != agent["lead"]:
            problems.append(f'"{agent_id}": lead cannot change — ignored')

        # Update editable fields
        if "name" in entry:
            name = str(entry["name"]).strip()
            if name:
                agent["name"] = name[:32].upper()
            else:
                problems.append(f'"{agent_id}": empty name — kept "{agent["name"]}"')

        if "role" in entry:
            agent["role"] = str(entry["role"]).strip()[:80]

        if "does" in entry:
            agent["does"] = str(entry["does"]).strip()[:400]

        if "tools" in entry:
            if isinstance(entry["tools"], list):
                agent["tools"] = [
                    str(t).strip() for t in entry["tools"] if str(t).strip()
                ][:12]
            else:
                problems.append(f'"{agent_id}": tools must be a list — ignored')

        if "brief" in entry:
            brief = str(entry["brief"]).strip()
            if len(brief) > BRIEF_MAX:
                problems.append(f'"{agent_id}": brief too long — truncated')
            agent["brief"] = brief[:BRIEF_MAX]

        if "model" in entry:
            model = str(entry.get("model", "")).lower().strip()
            if model in VALID_MODELS:
                agent["model"] = model
            elif model:
                problems.append(
                    f'"{agent_id}": invalid model "{model}" — kept "{agent.get("model", "default")}"'
                )

        if "effort" in entry:
            effort = str(entry.get("effort", "")).lower().strip()
            if effort in VALID_EFFORTS:
                agent["effort"] = effort
            elif effort:
                problems.append(f'"{agent_id}": invalid effort "{effort}" — kept')

    return output, problems


def load_roster(brain_path: Path = None) -> Dict[str, Any]:
    """Load roster from files

    Returns: {agents, problems, customised, briefed, files}
    """

    config = get_config()
    if brain_path is None:
        brain_path = config["brain_path"]

    root = config["brain_path"].parent

    files = [
        root / "office.agents.json",
        brain_path / "Agents Office" / "agents.json",
        root / "office.agents.local.json",
    ]

    agents = AGENTS_DEFAULTS.copy()
    problems = []

    for file_path in files:
        if not file_path.exists():
            continue

        doc = read_json(file_path)
        if not doc:
            continue

        validated, file_problems = validate_agents(doc, agents)
        agents = validated

        for prob in file_problems:
            problems.append(f"{file_path.name}: {prob}")

    # Count customized
    customized = sum(
        1
        for a in agents
        if a.get("brief")
        or any(
            a.get(k) != default.get(k)
            for k in {"name", "role", "does"}
            for default in [AGENTS_DEFAULTS[0]]
        )
    )

    briefed = sum(1 for a in agents if a.get("brief"))

    return {
        "agents": agents,
        "problems": problems,
        "customized": customized,
        "briefed": briefed,
        "files": [f.name for f in files if f.exists()],
    }


def get_agent(agent_id: str) -> Dict | None:
    """Get single agent by ID"""
    roster = load_roster()
    return next((a for a in roster["agents"] if a["id"] == agent_id), None)


def get_agents_by_dept(department: str) -> List[Dict]:
    """Get all agents in a department"""
    roster = load_roster()
    return [a for a in roster["agents"] if a["department"] == department]
