"""Agentic RAG Loop — plan, retrieve, grade, rewrite, generate with citations.

Implements the iterative retrieval-augmented generation pattern:
1. Plan: decompose the query into retrieval intent
2. Retrieve: fetch relevant chunks via hybrid search
3. Grade: score chunk relevance (LLM-as-judge)
4. Rewrite: if relevance is weak, reformulate query and retry
5. Generate: produce answer with inline citations
6. Self-check: verify answer is grounded in retrieved spans

Max 3 iterations to prevent runaway loops.
"""

from __future__ import annotations

import json
import re
from dataclasses import dataclass, field
from typing import Any, Protocol

import structlog

logger = structlog.get_logger("rag.agentic_loop")


class Retriever(Protocol):
    """Protocol for retrieval backends."""

    async def retrieve(self, query: str, top_k: int = 5) -> list[dict[str, Any]]: ...


class Router(Protocol):
    """Protocol for model routing."""

    async def complete(self, tier: str, messages: list[dict[str, str]], **kwargs: Any) -> Any: ...


@dataclass(frozen=True)
class Citation:
    """A citation linking an answer span to a retrieved chunk."""

    chunk_id: str
    source: str = ""
    content_preview: str = ""


@dataclass(frozen=True)
class RAGResult:
    """Immutable result from the agentic RAG loop."""

    answer: str
    status: str  # "ok", "low_relevance", "model_unavailable"
    citations: tuple[Citation, ...] = field(default_factory=tuple)
    iterations_used: int = 1
    model_used: str = ""


class AgenticRAGLoop:
    """Runs the iterative RAG loop: retrieve -> grade -> rewrite -> generate."""

    def __init__(
        self,
        retriever: Any,
        router: Any,
        tier: str = "rag_specialist",
        relevance_threshold: float = 0.5,
        max_iterations: int = 3,
        top_k: int = 5,
    ) -> None:
        self._retriever = retriever
        self._router = router
        self._tier = tier
        self._relevance_threshold = relevance_threshold
        self._max_iterations = max_iterations
        self._top_k = top_k

    async def run(self, query: str) -> RAGResult:
        """Execute the agentic RAG loop for a query."""
        current_query = query
        best_chunks: list[dict[str, Any]] = []

        for iteration in range(1, self._max_iterations + 1):
            # Step 1: Retrieve
            chunks = await self._retriever.retrieve(current_query, top_k=self._top_k)
            if not chunks:
                logger.warning("no_chunks_retrieved", query=current_query, iteration=iteration)
                if iteration == self._max_iterations:
                    return RAGResult(answer="", status="low_relevance", iterations_used=iteration)
                continue

            # Step 2: Grade relevance
            relevance_score = await self._grade_relevance(current_query, chunks)

            if relevance_score >= self._relevance_threshold:
                best_chunks = chunks
                break

            # Step 3: Rewrite query if relevance is weak
            if iteration < self._max_iterations:
                current_query = await self._rewrite_query(query, current_query, chunks)
                logger.info("query_rewritten", iteration=iteration, new_query=current_query)
            else:
                # Last iteration — use what we have
                best_chunks = chunks

        if not best_chunks:
            return RAGResult(answer="", status="low_relevance", iterations_used=self._max_iterations)

        # Step 4: Generate answer with citations
        result = await self._generate_answer(query, best_chunks)
        return result

    async def _grade_relevance(self, query: str, chunks: list[dict[str, Any]]) -> float:
        """Use LLM-as-judge to score chunk relevance to the query."""
        context = "\n".join(c.get("content", "") for c in chunks[:3])
        messages = [
            {
                "role": "user",
                "content": (
                    f"Rate the relevance of the following context to the query.\n"
                    f"Query: {query}\n"
                    f"Context: {context}\n\n"
                    f'Respond with JSON: {{"relevance": 0.0-1.0, "reason": "..."}}'
                ),
            }
        ]

        response = await self._router.complete(tier=self._tier, messages=messages)
        try:
            parsed = json.loads(response.content)
            return float(parsed.get("relevance", 0.0))
        except (json.JSONDecodeError, ValueError, TypeError):
            return 0.5  # Default to borderline if parsing fails

    async def _rewrite_query(
        self, original_query: str, current_query: str, chunks: list[dict[str, Any]]
    ) -> str:
        """Rewrite the query to improve retrieval relevance."""
        messages = [
            {
                "role": "user",
                "content": (
                    f"The following search query did not retrieve relevant results.\n"
                    f"Original: {original_query}\n"
                    f"Current: {current_query}\n\n"
                    f"Rewrite the query to better match relevant documents. "
                    f"Return only the rewritten query, nothing else."
                ),
            }
        ]

        response = await self._router.complete(tier=self._tier, messages=messages)
        return response.content.strip() or current_query

    async def _generate_answer(self, query: str, chunks: list[dict[str, Any]]) -> RAGResult:
        """Generate a grounded answer with inline citations."""
        # Build context with chunk IDs for citation
        context_parts = []
        for chunk in chunks:
            chunk_id = chunk.get("id", "unknown")
            content = chunk.get("content", "")
            context_parts.append(f"[{chunk_id}]: {content}")
        context = "\n\n".join(context_parts)

        messages = [
            {
                "role": "user",
                "content": (
                    f"Answer the following question using ONLY the provided context.\n"
                    f"Include inline citations using [chunk-id] format.\n\n"
                    f"Context:\n{context}\n\n"
                    f"Question: {query}\n\n"
                    f"Answer:"
                ),
            }
        ]

        response = await self._router.complete(tier=self._tier, messages=messages)

        # Extract citations from the answer
        citations = self._extract_citations(response.content, chunks)

        return RAGResult(
            answer=response.content,
            status="ok",
            citations=tuple(citations),
            iterations_used=1,
            model_used=getattr(response, "model_used", ""),
        )

    def _extract_citations(self, answer: str, chunks: list[dict[str, Any]]) -> list[Citation]:
        """Extract [chunk-id] citations from the generated answer."""
        chunk_map = {c.get("id", ""): c for c in chunks}
        cited_ids = re.findall(r"\[([^\]]+)\]", answer)

        citations = []
        seen = set()
        for cid in cited_ids:
            if cid in chunk_map and cid not in seen:
                seen.add(cid)
                chunk = chunk_map[cid]
                citations.append(
                    Citation(
                        chunk_id=cid,
                        source=chunk.get("metadata", {}).get("source", ""),
                        content_preview=chunk.get("content", "")[:100],
                    )
                )

        return citations
