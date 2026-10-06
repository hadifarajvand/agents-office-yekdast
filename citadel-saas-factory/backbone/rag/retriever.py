"""Hybrid retriever — combines vector similarity and keyword search with reranking.

Uses reciprocal rank fusion when no reranker model is available.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

import structlog
import yaml

from backbone.rag.store import SearchResult, VectorStore
from backbone.rag.embeddings import EmbeddingService

logger = structlog.get_logger("rag.retriever")


def reciprocal_rank_fusion(
    result_lists: list[list[SearchResult]],
    k: int = 60,
) -> list[SearchResult]:
    """Merge multiple ranked lists using RRF scoring."""
    scores: dict[str, float] = {}
    result_map: dict[str, SearchResult] = {}

    for results in result_lists:
        for rank, result in enumerate(results):
            scores[result.id] = scores.get(result.id, 0.0) + 1.0 / (k + rank + 1)
            result_map[result.id] = result

    sorted_ids = sorted(scores, key=lambda x: scores[x], reverse=True)
    return [
        SearchResult(
            id=rid,
            content=result_map[rid].content,
            metadata=result_map[rid].metadata,
            score=scores[rid],
        )
        for rid in sorted_ids
    ]


class HybridRetriever:
    """Retrieves documents using both vector and keyword search, then reranks."""

    def __init__(
        self,
        store: VectorStore,
        embedding_service: EmbeddingService,
        reranker_config_path: Path | None = None,
        top_k: int = 10,
    ) -> None:
        self._store = store
        self._embedding_service = embedding_service
        self._top_k = top_k

        repo_root = Path(__file__).resolve().parents[2]
        config_path = reranker_config_path or repo_root / "models" / "rerankers.yaml"
        self._reranker_config = self._load_config(config_path)

    @staticmethod
    def _load_config(path: Path) -> dict[str, Any]:
        if path.exists():
            with open(path) as f:
                return yaml.safe_load(f) or {}
        return {}

    async def retrieve(self, query: str, top_k: int | None = None) -> list[dict[str, Any]]:
        """Hybrid retrieve: vector + keyword, merged with RRF, optionally reranked."""
        k = top_k or self._top_k

        # Parallel retrieval
        query_embedding = await self._embedding_service.embed_query(query)
        vector_results = await self._store.search_vector(query_embedding, top_k=k * 2)
        keyword_results = await self._store.search_keyword(query, top_k=k * 2)

        # Merge with reciprocal rank fusion
        merged = reciprocal_rank_fusion([vector_results, keyword_results])

        # Truncate to top_k
        top_results = merged[:k]

        # Convert to dict format for the agentic loop
        return [
            {
                "id": r.id,
                "content": r.content,
                "metadata": r.metadata,
                "score": r.score,
            }
            for r in top_results
        ]
