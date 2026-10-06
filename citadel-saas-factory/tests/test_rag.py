"""Tests for the RAG agentic loop — retrieval, grading, and citation generation."""

from __future__ import annotations

import pytest
from unittest.mock import AsyncMock, MagicMock


@pytest.fixture
def fixture_corpus() -> list[dict]:
    """A tiny corpus for testing retrieval and generation."""
    return [
        {
            "id": "chunk-001",
            "content": "PostgreSQL 16 supports HNSW indexes for vector similarity search via pgvector.",
            "metadata": {"source": "docs/database.md", "page": 1},
        },
        {
            "id": "chunk-002",
            "content": "Redis 7 provides pub/sub messaging and can be used as a cache layer.",
            "metadata": {"source": "docs/cache.md", "page": 1},
        },
        {
            "id": "chunk-003",
            "content": "Keycloak 24 handles OAuth2, RBAC, and MFA for authentication.",
            "metadata": {"source": "docs/auth.md", "page": 1},
        },
    ]


class TestAgenticLoop:
    """Test the plan-retrieve-grade-generate loop."""

    @pytest.mark.asyncio
    async def test_loop_retrieves_and_generates_with_citation(self, fixture_corpus):
        from backbone.rag.agentic_loop import AgenticRAGLoop

        mock_retriever = AsyncMock()
        mock_retriever.retrieve.return_value = [fixture_corpus[0]]

        mock_router = AsyncMock()
        mock_router.complete.return_value = MagicMock(
            content="PostgreSQL 16 supports HNSW indexes for vector search [chunk-001].",
            status="ok",
            model_used="anthropic/claude-sonnet-4-20250514",
            prompt_tokens=100,
            completion_tokens=50,
        )

        loop = AgenticRAGLoop(retriever=mock_retriever, router=mock_router)
        result = await loop.run(query="How does vector search work in the database?")

        assert result.answer != ""
        assert result.status == "ok"
        assert len(result.citations) >= 1
        assert result.citations[0].chunk_id == "chunk-001"
        mock_retriever.retrieve.assert_called()

    @pytest.mark.asyncio
    async def test_loop_rewrites_query_on_weak_relevance(self, fixture_corpus):
        from backbone.rag.agentic_loop import AgenticRAGLoop

        call_count = {"retrieve": 0}

        async def mock_retrieve(query: str, top_k: int = 5):
            call_count["retrieve"] += 1
            if call_count["retrieve"] == 1:
                return [fixture_corpus[1]]
            return [fixture_corpus[0]]

        mock_retriever = AsyncMock()
        mock_retriever.retrieve = AsyncMock(side_effect=mock_retrieve)

        mock_router = AsyncMock()
        responses = [
            MagicMock(content='{"relevance": 0.3, "reason": "Off topic"}', status="ok"),
            MagicMock(content="PostgreSQL HNSW vector index", status="ok"),
            MagicMock(content='{"relevance": 0.9, "reason": "Directly relevant"}', status="ok"),
            MagicMock(
                content="PostgreSQL supports HNSW indexes [chunk-001].",
                status="ok",
                model_used="anthropic/claude-sonnet-4-20250514",
                prompt_tokens=100,
                completion_tokens=50,
            ),
        ]
        mock_router.complete = AsyncMock(side_effect=responses)

        loop = AgenticRAGLoop(
            retriever=mock_retriever,
            router=mock_router,
            relevance_threshold=0.5,
        )
        result = await loop.run(query="How does pgvector work?")

        assert call_count["retrieve"] >= 2
        assert result.status == "ok"

    @pytest.mark.asyncio
    async def test_loop_max_iterations_cap(self, fixture_corpus):
        from backbone.rag.agentic_loop import AgenticRAGLoop

        mock_retriever = AsyncMock()
        mock_retriever.retrieve = AsyncMock(return_value=[fixture_corpus[1]])

        mock_router = AsyncMock()
        mock_router.complete = AsyncMock(
            return_value=MagicMock(content='{"relevance": 0.1, "reason": "Not relevant"}', status="ok")
        )

        loop = AgenticRAGLoop(
            retriever=mock_retriever,
            router=mock_router,
            relevance_threshold=0.5,
            max_iterations=3,
        )
        result = await loop.run(query="Something totally unrelated")

        assert result.status in ("ok", "low_relevance")
        assert mock_retriever.retrieve.call_count <= 3
