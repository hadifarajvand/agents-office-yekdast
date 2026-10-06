"""Structure-aware text chunker with token-bounded splitting and overlap.

Splits documents into chunks respecting paragraph and heading boundaries,
with configurable max tokens and overlap for retrieval continuity.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Any


@dataclass(frozen=True)
class Chunk:
    """A token-bounded text chunk with metadata."""

    id: str
    content: str
    token_count: int
    metadata: dict[str, Any]


def estimate_tokens(text: str) -> int:
    """Rough token estimate: ~4 chars per token for English text."""
    return max(1, len(text) // 4)


def chunk_document(
    text: str,
    source: str = "",
    max_tokens: int = 512,
    overlap_tokens: int = 50,
    doc_metadata: dict[str, Any] | None = None,
) -> list[Chunk]:
    """Split a document into structure-aware chunks.

    Strategy:
    1. Split on double newlines (paragraphs) and headings
    2. Accumulate paragraphs until max_tokens is reached
    3. Overlap last N tokens from previous chunk into next
    """
    metadata = doc_metadata or {}
    metadata["source"] = source

    # Split on paragraph boundaries and headings
    blocks = re.split(r"\n\s*\n|(?=^#{1,6}\s)", text, flags=re.MULTILINE)
    blocks = [b.strip() for b in blocks if b.strip()]

    chunks: list[Chunk] = []
    current_blocks: list[str] = []
    current_tokens = 0
    chunk_idx = 0

    for block in blocks:
        block_tokens = estimate_tokens(block)

        if current_tokens + block_tokens > max_tokens and current_blocks:
            # Emit current chunk
            content = "\n\n".join(current_blocks)
            chunks.append(
                Chunk(
                    id=f"{source}:chunk-{chunk_idx:04d}" if source else f"chunk-{chunk_idx:04d}",
                    content=content,
                    token_count=current_tokens,
                    metadata={**metadata, "chunk_index": chunk_idx},
                )
            )
            chunk_idx += 1

            # Overlap: keep last block if within overlap budget
            if overlap_tokens > 0 and current_blocks:
                last = current_blocks[-1]
                if estimate_tokens(last) <= overlap_tokens:
                    current_blocks = [last]
                    current_tokens = estimate_tokens(last)
                else:
                    current_blocks = []
                    current_tokens = 0
            else:
                current_blocks = []
                current_tokens = 0

        current_blocks.append(block)
        current_tokens += block_tokens

    # Emit final chunk
    if current_blocks:
        content = "\n\n".join(current_blocks)
        chunks.append(
            Chunk(
                id=f"{source}:chunk-{chunk_idx:04d}" if source else f"chunk-{chunk_idx:04d}",
                content=content,
                token_count=current_tokens,
                metadata={**metadata, "chunk_index": chunk_idx},
            )
        )

    return chunks
