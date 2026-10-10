"""Prototype bridge to Citadel's backbone (vendored at citadel-saas-factory/backbone).

Off unless AO_BACKBONE=1. When on, every metered model call is also recorded in
Citadel's SafetyGovernor (token/cost/tool ceilings and the kill switch). Pure code:
no extra model calls, no extra prompt text. PLAN §19.1.
"""
from __future__ import annotations

import os
import sys
from pathlib import Path

_ROOT = Path(__file__).resolve().parents[2] / "citadel-saas-factory"
_governor = None


def enabled() -> bool:
    return os.environ.get("AO_BACKBONE") == "1"


def governor():
    global _governor
    if _governor is None:
        if str(_ROOT) not in sys.path:
            sys.path.insert(0, str(_ROOT))
        from backbone.policies.safety import SafetyConfig, SafetyGovernor
        _governor = SafetyGovernor(SafetyConfig(
            max_tokens_per_run=int(os.environ.get("AO_BACKBONE_MAX_TOKENS", "500000")),
            max_cost_usd_per_run=float(os.environ.get("AO_BACKBONE_MAX_USD", "10")),
        ))
    return _governor


def reset() -> None:
    global _governor
    _governor = None


def charge(run_id: str, tokens: int, usd: float) -> str | None:
    """Record usage; return a reason when the governor says the run must stop."""
    if not enabled():
        return None
    g = governor()
    # The dollar ceiling guards task and routine runs. A job stage already answers to its lane
    # budget (graph.py RunMeter usd_cap), so only its tokens and the kill switch are governed here.
    g.record_usage(run_id or "unlabelled", tokens=tokens, cost_usd=0.0 if (run_id or "").startswith("job:") else usd)
    verdict = g.check_budget(run_id or "unlabelled")
    return None if verdict["allowed"] else str(verdict["reason"])


# Our pipeline role -> Citadel tier (see seed/backbone/routing.yaml).
ROLE_TIER = {"builder": "reasoning_fast", "tests": "reasoning_fast", "lead_review": "reasoning_deep",
             "research": "rag_specialist", "drafts": "reasoning_fast", "router": "cheap_fast", "chat": "cheap_fast"}
_router = None


def router():
    """Citadel's ModelRouter over our routing.yaml. select() needs no litellm; we never call complete()."""
    global _router
    if _router is None:
        if str(_ROOT) not in sys.path:
            sys.path.insert(0, str(_ROOT))
        from backbone.runtime.model_client import ModelRouter
        seed = Path(__file__).resolve().parent / "seed" / "backbone"
        _router = ModelRouter(routing_path=seed / "routing.yaml", catalog_path=seed / "catalog.yaml")
    return _router


def model_for_role(role: str) -> str | None:
    """Model id from the tier table when the bridge is on and the role is known, else None."""
    if not enabled() or role not in ROLE_TIER:
        return None
    return router().select(ROLE_TIER[role]).primary


OWNER_RISKS = ("high", "deploy", "owner")


def requires_owner(risk: str) -> bool:
    """Citadel's approval_gate autonomy level: low and medium risk run, high and deploy wait for the owner.
    The owner-only release step is never reachable by an agent whatever this answers."""
    return risk in OWNER_RISKS
