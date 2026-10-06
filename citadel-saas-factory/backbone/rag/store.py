"""Vector store backed by pgvector — HNSW index with metadata JSONB + GIN index.

Reuses the PostgreSQL service from docker-compose.yml. Requires the pgvector
extension to be installed (CREATE EXTENSION vector).
"""

from __future__ import annotations

import json
from dataclasses import dataclass
from typing import Any

import structlog

logger = structlog.get_logger("rag.store")

# SQL for initialization
INIT_SQL = """
CREATE EXTENSION IF NOT EXISTS vector;

CREATE TABLE IF NOT EXISTS rag_chunks (
    id TEXT PRIMARY KEY,
    content TEXT NOT NULL,
    embedding vector({dimensions}),
    metadata JSONB DEFAULT '{{}}'::jsonb,
    token_count INTEGER DEFAULT 0,
    created_at TIMESTAMPTZ DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_chunks_embedding
    ON rag_chunks USING hnsw (embedding vector_cosine_ops)
    WITH (m = 16, ef_construction = 200);

CREATE INDEX IF NOT EXISTS idx_chunks_metadata
    ON rag_chunks USING gin (metadata);

CREATE INDEX IF NOT EXISTS idx_chunks_content_trgm
    ON rag_chunks USING gin (content gin_trgm_ops);
"""

UPSERT_SQL = """
INSERT INTO rag_chunks (id, content, embedding, metadata, token_count)
VALUES ($1, $2, $3, $4, $5)
ON CONFLICT (id) DO UPDATE SET
    content = EXCLUDED.content,
    embedding = EXCLUDED.embedding,
    metadata = EXCLUDED.metadata,
    token_count = EXCLUDED.token_count;
"""

SEARCH_SQL = """
SELECT id, content, metadata, token_count,
       1 - (embedding <=> $1::vector) AS similarity
FROM rag_chunks
ORDER BY embedding <=> $1::vector
LIMIT $2;
"""

KEYWORD_SEARCH_SQL = """
SELECT id, content, metadata, token_count,
       ts_rank(to_tsvector('english', content), plainto_tsquery('english', $1)) AS rank
FROM rag_chunks
WHERE to_tsvector('english', content) @@ plainto_tsquery('english', $1)
ORDER BY rank DESC
LIMIT $2;
"""


@dataclass(frozen=True)
class SearchResult:
    """A single search result from the vector store."""

    id: str
    content: str
    metadata: dict[str, Any]
    score: float


class VectorStore:
    """pgvector-backed store with HNSW index and hybrid search."""

    def __init__(self, dsn: str | None = None, dimensions: int = 1024) -> None:
        import os

        self._dsn = dsn or os.getenv(
            "DATABASE_URL",
            "postgresql://citadel:citadel@localhost:5432/citadel",
        )
        # Convert asyncpg:// format if present
        self._dsn = self._dsn.replace("postgresql+asyncpg://", "postgresql://")
        self._dimensions = dimensions
        self._pool = None

    async def initialize(self) -> None:
        """Create tables and indexes if they do not exist."""
        import asyncpg

        self._pool = await asyncpg.create_pool(self._dsn, min_size=2, max_size=10)
        async with self._pool.acquire() as conn:
            # pg_trgm needed for keyword search
            await conn.execute("CREATE EXTENSION IF NOT EXISTS pg_trgm;")
            await conn.execute(INIT_SQL.format(dimensions=self._dimensions))
        logger.info("vector_store_initialized", dimensions=self._dimensions)

    async def upsert(
        self,
        chunk_id: str,
        content: str,
        embedding: list[float],
        metadata: dict[str, Any] | None = None,
        token_count: int = 0,
    ) -> None:
        """Insert or update a chunk in the store."""
        if self._pool is None:
            raise RuntimeError("Store not initialized. Call initialize() first.")

        embedding_str = "[" + ",".join(str(v) for v in embedding) + "]"
        meta_json = json.dumps(metadata or {})

        async with self._pool.acquire() as conn:
            await conn.execute(UPSERT_SQL, chunk_id, content, embedding_str, meta_json, token_count)

    async def search_vector(self, query_embedding: list[float], top_k: int = 10) -> list[SearchResult]:
        """Search by vector similarity using HNSW index."""
        if self._pool is None:
            raise RuntimeError("Store not initialized.")

        embedding_str = "[" + ",".join(str(v) for v in query_embedding) + "]"

        async with self._pool.acquire() as conn:
            rows = await conn.fetch(SEARCH_SQL, embedding_str, top_k)

        return [
            SearchResult(
                id=row["id"],
                content=row["content"],
                metadata=json.loads(row["metadata"]) if isinstance(row["metadata"], str) else row["metadata"],
                score=float(row["similarity"]),
            )
            for row in rows
        ]

    async def search_keyword(self, query: str, top_k: int = 10) -> list[SearchResult]:
        """Search by full-text keyword matching."""
        if self._pool is None:
            raise RuntimeError("Store not initialized.")

        async with self._pool.acquire() as conn:
            rows = await conn.fetch(KEYWORD_SEARCH_SQL, query, top_k)

        return [
            SearchResult(
                id=row["id"],
                content=row["content"],
                metadata=json.loads(row["metadata"]) if isinstance(row["metadata"], str) else row["metadata"],
                score=float(row["rank"]),
            )
            for row in rows
        ]

    async def close(self) -> None:
        """Close the connection pool."""
        if self._pool:
            await self._pool.close()
