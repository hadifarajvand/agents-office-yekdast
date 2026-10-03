"""Who must approve what. Separation of duties is enforced here, in code:

  - whoever builds cannot approve exposure (engineering, frontend, devops leads never);
  - exposure needs a security verdict AND commercial consent from two different seats;
  - the owner must also click the first N Tier 1 previews, and every Tier 2 one;
  - Tier 2 (open public / production) is never delegated.
"""
from __future__ import annotations

OWNER = "owner"
BUILDER_DEPTS = {"engineering", "frontend", "devops"}
TIER_NAMES = {0: "private", 1: "gated", 2: "public"}


def stage_lead(cfg, stage: str) -> str:
    for s in cfg.pipeline.get("stages", []):
        if s["name"] == stage:
            return s["lead"]
    raise KeyError(stage)


def owner_gates(cfg) -> list[str]:
    return list(cfg.pipeline.get("owner_gates", ["verify", "handoff"]))


def exposure_keys(cfg) -> dict:
    return dict(cfg.exposure.get("keys") or {})


def stage_roles(cfg, stage: str, *, tier: int = 0, owner_clicks: int = 0) -> list[str]:
    """Every role whose PASS is required before `stage` may advance."""
    if stage == "exposure":
        if tier <= 0:
            return []
        keys = exposure_keys(cfg)
        roles = [keys["security"], keys["commercial"]]
        if tier >= 2 or owner_clicks < int(cfg.exposure.get("tier1_owner_clicks", 3)):
            roles.append(OWNER)
        return roles
    roles = [stage_lead(cfg, stage)]
    if stage in owner_gates(cfg):
        roles.append(OWNER)
    return roles


def can_approve(cfg, role: str, stage: str) -> bool:
    if role == OWNER:
        return True
    if stage == "exposure":
        return role in exposure_keys(cfg).values()
    return role == stage_lead(cfg, stage)


def validate_config(cfg, agents: list) -> list[str]:
    """Problems with the pipeline/exposure config; empty when it is safe to run."""
    problems: list[str] = []
    by_id = {a.id: a for a in agents}
    names = [s["name"] for s in cfg.pipeline.get("stages", [])]
    for need in ("intake", "verify", "scope", "build", "security", "preview", "exposure", "handoff"):
        if need not in names:
            problems.append(f'pipeline.stages is missing "{need}"')
    for s in cfg.pipeline.get("stages", []):
        a = by_id.get(s["lead"])
        if not a:
            problems.append(f'stage {s["name"]}: lead "{s["lead"]}" is not a seat')
        elif not a.lead:
            problems.append(f'stage {s["name"]}: "{s["lead"]}" is not a department lead')
        elif a.department != s["dept"]:
            problems.append(f'stage {s["name"]}: {s["lead"]} is in {a.department}, not {s["dept"]}')
    keys = exposure_keys(cfg)
    if set(keys) != {"security", "commercial"}:
        problems.append('exposure.keys must name exactly "security" and "commercial"')
    else:
        if keys["security"] == keys["commercial"]:
            problems.append("exposure keys must be two different seats")
        for k, who in keys.items():
            a = by_id.get(who)
            if not a or not a.lead:
                problems.append(f'exposure key {k}: "{who}" is not a department lead')
            elif a.department in BUILDER_DEPTS:
                problems.append(f'exposure key {k}: {who} is in {a.department}; builders cannot approve exposure')
    return problems
