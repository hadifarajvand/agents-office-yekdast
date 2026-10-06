"""Multi-model client with tier-based routing, fallback chains, and budget control.

Reads models/routing.yaml for tier definitions and models/catalog.yaml for
provider mappings. Routes agent calls through LiteLLM with automatic fallback
and daily budget enforcement.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import structlog
import yaml

logger = structlog.get_logger("model_client")

# Lazy import — only pulled when complete() is actually called
acompletion = None


def _ensure_litellm() -> None:
    global acompletion
    if acompletion is None:
        from litellm import acompletion as _ac  # noqa: N812
        acompletion = _ac


@dataclass(frozen=True)
class TierSelection:
    """Resolved tier with LiteLLM model ids ready to call."""

    tier_name: str
    primary: str
    fallbacks: list[str]
    max_tokens: int
    temperature: float


@dataclass(frozen=True)
class CompletionResult:
    """Immutable result from a model call."""

    content: str
    status: str  # "ok", "model_unavailable", "budget_exceeded"
    model_used: str = ""
    prompt_tokens: int = 0
    completion_tokens: int = 0
    estimated_cost_usd: float = 0.0


class ModelRouter:
    """Routes agent calls to models by tier with fallback and budget control.

    Usage:
        router = ModelRouter()
        result = await router.complete("reasoning_fast", messages=[...])
    """

    def __init__(
        self,
        routing_path: Path | None = None,
        catalog_path: Path | None = None,
    ) -> None:
        repo_root = Path(__file__).resolve().parents[2]
        self._routing_path = routing_path or repo_root / "models" / "routing.yaml"
        self._catalog_path = catalog_path or repo_root / "models" / "catalog.yaml"

        self._routing = self._load_yaml(self._routing_path)
        self._catalog = self._load_yaml(self._catalog_path)

        # Build lookup: model_id -> litellm_id
        self._model_map: dict[str, str] = {}
        self._cost_map: dict[str, dict[str, float]] = {}
        for model_id, info in self._catalog.get("models", {}).items():
            self._model_map[model_id] = info["litellm_id"]
            self._cost_map[model_id] = {
                "input": info.get("cost_per_1k_input", 0.0),
                "output": info.get("cost_per_1k_output", 0.0),
            }

        # Budget tracking (in-process, resets on restart)
        cost_controls = self._routing.get("cost_controls", {})
        self._daily_budget_usd: float = cost_controls.get("daily_budget_usd", 50.0)
        self._warn_at_pct: float = cost_controls.get("warn_at_pct", 80)
        self._daily_spend_usd: float = 0.0

    @staticmethod
    def _load_yaml(path: Path) -> dict[str, Any]:
        with open(path) as f:
            return yaml.safe_load(f) or {}

    def select(self, tier: str) -> TierSelection:
        """Resolve a tier name to a TierSelection with LiteLLM model ids.

        Raises KeyError if the tier is not defined in routing.yaml.
        """
        tiers = self._routing.get("tiers", {})
        if tier not in tiers:
            raise KeyError(f"Unknown tier: {tier!r}. Available: {list(tiers.keys())}")

        tier_cfg = tiers[tier]
        primary_id = tier_cfg["primary"]
        fallback_ids = tier_cfg.get("fallbacks", [])

        return TierSelection(
            tier_name=tier,
            primary=self._model_map.get(primary_id, primary_id),
            fallbacks=[self._model_map.get(fid, fid) for fid in fallback_ids],
            max_tokens=tier_cfg.get("max_tokens", 4096),
            temperature=tier_cfg.get("temperature", 0.2),
        )

    def _estimate_cost(self, model_litellm_id: str, prompt_tokens: int, completion_tokens: int) -> float:
        """Estimate cost in USD for a completion call."""
        # Reverse lookup: litellm_id -> model_id
        model_id = None
        for mid, lid in self._model_map.items():
            if lid == model_litellm_id:
                model_id = mid
                break
        if model_id is None:
            return 0.0

        costs = self._cost_map.get(model_id, {})
        input_cost = (prompt_tokens / 1000) * costs.get("input", 0.0)
        output_cost = (completion_tokens / 1000) * costs.get("output", 0.0)
        return input_cost + output_cost

    async def complete(
        self,
        tier: str,
        messages: list[dict[str, str]],
        **kwargs: Any,
    ) -> CompletionResult:
        """Call a model by tier with fallback and budget control.

        If budget is exceeded, routes to local_only tier.
        If all models fail, returns status="model_unavailable".
        """
        _ensure_litellm()

        # Budget check — route to local_only if exceeded
        if self._daily_spend_usd >= self._daily_budget_usd:
            tiers = self._routing.get("tiers", {})
            if "local_only" in tiers and tier != "local_only":
                logger.warning(
                    "budget_exceeded",
                    daily_spend=self._daily_spend_usd,
                    budget=self._daily_budget_usd,
                    original_tier=tier,
                    routed_to="local_only",
                )
                tier = "local_only"

        selection = self.select(tier)
        models_to_try = [selection.primary] + selection.fallbacks

        last_error: Exception | None = None
        for model_id in models_to_try:
            try:
                response = await acompletion(
                    model=model_id,
                    messages=messages,
                    max_tokens=selection.max_tokens,
                    temperature=selection.temperature,
                    **kwargs,
                )

                content = response.choices[0].message.content or ""
                prompt_tokens = response.usage.prompt_tokens
                completion_tokens = response.usage.completion_tokens
                est_cost = self._estimate_cost(model_id, prompt_tokens, completion_tokens)
                self._daily_spend_usd += est_cost

                if self._daily_spend_usd >= self._daily_budget_usd * (self._warn_at_pct / 100):
                    logger.warning(
                        "budget_warning",
                        daily_spend=self._daily_spend_usd,
                        budget=self._daily_budget_usd,
                        pct=round(self._daily_spend_usd / self._daily_budget_usd * 100, 1),
                    )

                logger.info(
                    "completion",
                    tier=selection.tier_name,
                    model=model_id,
                    prompt_tokens=prompt_tokens,
                    completion_tokens=completion_tokens,
                    est_cost_usd=round(est_cost, 6),
                    latency_ms=None,  # Would need timing wrapper
                )

                return CompletionResult(
                    content=content,
                    status="ok",
                    model_used=model_id,
                    prompt_tokens=prompt_tokens,
                    completion_tokens=completion_tokens,
                    estimated_cost_usd=est_cost,
                )

            except Exception as exc:
                last_error = exc
                logger.warning(
                    "model_fallback",
                    model=model_id,
                    error=str(exc),
                    remaining=len(models_to_try) - models_to_try.index(model_id) - 1,
                )

        # All models failed
        logger.error(
            "all_models_failed",
            tier=tier,
            models_tried=models_to_try,
            last_error=str(last_error),
        )
        return CompletionResult(
            content="",
            status="model_unavailable",
        )
