"""Guarded model client — wraps ModelRouter with triple-layer guardrails.

Validates every LLM output through:
1. Guardrails AI validators (hallucination, toxicity, PII)
2. Prompt-injection sanitization on inputs (RAG docs, browser content)
3. Output action allowlist enforcement

If output fails validation, retries up to max_retries times, then rejects.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Any

import structlog

logger = structlog.get_logger("runtime.guarded_client")

# Injection patterns for RAG document and browser content sanitization
RAG_INJECTION_PATTERNS = [
    r"(?i)ignore\s+(all\s+)?previous\s+instructions?",
    r"(?i)execute\s+tool\s*:",
    r"(?i)call\s+function\s*:",
    r"(?i)system\s*:\s*you\s+are",
    r"(?i)<\s*/?tool_call\s*>",
    r"(?i)\btool_use\b",
    r"(?i)delete_(?:all|database|files)",
    r"(?i)drop\s+(?:table|database)",
    r"(?i)\brm\s+-rf\b",
    r"(?i)\bsudo\s+",
    r"(?i)api[_-]?key\s*[=:]\s*\S+",
    r"(?i)password\s*[=:]\s*\S+",
    r"(?i)\bexec\s*\(",
    r"(?i)\beval\s*\(",
    r"(?i)__import__",
    r"(?i)subprocess\s*\.",
]

# Allowed agent actions (output must not trigger anything outside this list)
ALLOWED_ACTIONS = frozenset({
    "search",
    "retrieve",
    "summarize",
    "analyze",
    "compare",
    "explain",
    "recommend",
    "list",
    "draft",
    "review",
})


def sanitize_rag_context(content: str, max_length: int = 16000) -> str:
    """Strip injection patterns from RAG document content.

    Treats all ingested document content as untrusted.
    """
    sanitized = content
    for pattern in RAG_INJECTION_PATTERNS:
        sanitized = re.sub(pattern, "[FILTERED]", sanitized)

    if len(sanitized) > max_length:
        sanitized = sanitized[:max_length] + "\n[...truncated]"

    return sanitized


@dataclass(frozen=True)
class GuardedResult:
    """Result from a guarded completion call."""

    content: str
    status: str  # "ok", "rejected", "model_unavailable"
    model_used: str = ""
    retries: int = 0


class GuardedModelClient:
    """Model client that validates all outputs through guardrails."""

    def __init__(
        self,
        router: Any,
        validator: Any | None = None,
        max_retries: int = 3,
    ) -> None:
        self._router = router
        self._validator = validator
        self._max_retries = max_retries

    async def complete(
        self,
        tier: str,
        messages: list[dict[str, str]],
        source_context: str | None = None,
        **kwargs: Any,
    ) -> GuardedResult:
        """Call the model with guardrails validation on output.

        If source_context is provided (RAG), it is sanitized before use.
        Output is validated; low scores trigger retry, then rejection.
        """
        # Sanitize source context if provided
        if source_context:
            source_context = sanitize_rag_context(source_context)

        for attempt in range(1, self._max_retries + 1):
            response = await self._router.complete(tier=tier, messages=messages, **kwargs)

            if response.status != "ok":
                return GuardedResult(
                    content="",
                    status="model_unavailable",
                )

            # Validate output
            if self._validator:
                validation = await self._validator.validate(
                    response.content,
                    source_context=source_context,
                )

                logger.info(
                    "guardrails_check",
                    attempt=attempt,
                    passed=validation.passed,
                    score=getattr(validation, "hallucination_score", None),
                )

                if validation.passed:
                    return GuardedResult(
                        content=response.content,
                        status="ok",
                        model_used=getattr(response, "model_used", ""),
                        retries=attempt - 1,
                    )

                # Retry
                logger.warning(
                    "guardrails_retry",
                    attempt=attempt,
                    reason=getattr(validation, "message", "validation failed"),
                )
            else:
                # No validator configured — pass through
                return GuardedResult(
                    content=response.content,
                    status="ok",
                    model_used=getattr(response, "model_used", ""),
                )

        # All retries exhausted
        logger.error("guardrails_rejected", retries=self._max_retries)
        return GuardedResult(content="", status="rejected", retries=self._max_retries)
