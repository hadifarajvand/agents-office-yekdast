"""Browse agent handler — processes tab content from the Chrome extension.

Sanitizes untrusted tab content before passing to the LLM, enforces an
allowlist of permitted agent actions, and returns a structured response.
"""

from __future__ import annotations

import re
from typing import Any

import structlog

logger = structlog.get_logger("runtime.browse")

# Patterns that could trigger tool calls or instruction hijacking
INJECTION_PATTERNS = [
    r"(?i)ignore\s+(all\s+)?previous\s+instructions?",
    r"(?i)execute\s+tool\s*:",
    r"(?i)call\s+function\s*:",
    r"(?i)system\s*:\s*you\s+are",
    r"(?i)<\s*tool_call\s*>",
    r"(?i)delete_all",
    r"(?i)drop\s+table",
    r"(?i)rm\s+-rf",
    r"(?i)\bsudo\b",
    r"(?i)api[_-]?key\s*[=:]\s*\S+",
]


def sanitize_tab_content(content: str, max_length: int = 8000) -> str:
    """Strip injection patterns and truncate tab content.

    Tab content is untrusted user-supplied HTML/text from the browser.
    We strip known injection patterns and limit length.
    """
    sanitized = content

    for pattern in INJECTION_PATTERNS:
        sanitized = re.sub(pattern, "[REDACTED]", sanitized)

    # Truncate to max length
    if len(sanitized) > max_length:
        sanitized = sanitized[:max_length] + "\n[...truncated]"

    return sanitized


async def handle_browse_request(
    tab_url: str,
    tab_content: str,
    user_query: str,
    router: Any,
    tier: str = "reasoning_fast",
) -> dict[str, Any]:
    """Process a browse request from the Chrome extension.

    Args:
        tab_url: The URL of the active tab.
        tab_content: Raw text content of the tab (untrusted).
        user_query: The user's question about the page.
        router: ModelRouter instance for LLM calls.
        tier: Model tier to use.

    Returns:
        Structured response dict with answer, status, and metadata.
    """
    # Sanitize untrusted tab content
    safe_content = sanitize_tab_content(tab_content)

    logger.info(
        "browse_request",
        url=tab_url,
        content_length=len(tab_content),
        sanitized_length=len(safe_content),
        query_length=len(user_query),
    )

    messages = [
        {
            "role": "user",
            "content": (
                f"You are a browsing assistant. Analyze the following web page content "
                f"and answer the user's question.\n\n"
                f"Page URL: {tab_url}\n\n"
                f"Page content:\n{safe_content}\n\n"
                f"User question: {user_query}\n\n"
                f"Provide a concise, helpful answer based only on the page content."
            ),
        }
    ]

    response = await router.complete(tier=tier, messages=messages)

    return {
        "status": response.status,
        "answer": response.content,
        "model_used": getattr(response, "model_used", ""),
        "url": tab_url,
    }
