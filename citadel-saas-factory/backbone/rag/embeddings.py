"""Embedding service — reads models/embeddings.yaml, batches requests.

Supports both API-based embeddings (Voyage) and local (Ollama).
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

import structlog
import yaml

logger = structlog.get_logger("rag.embeddings")


class EmbeddingService:
    """Generate embeddings for text chunks using configured models."""

    def __init__(self, config_path: Path | None = None) -> None:
        repo_root = Path(__file__).resolve().parents[2]
        self._config_path = config_path or repo_root / "models" / "embeddings.yaml"
        self._config = self._load_config()

    def _load_config(self) -> dict[str, Any]:
        with open(self._config_path) as f:
            return yaml.safe_load(f) or {}

    @property
    def dimensions(self) -> int:
        primary = self._config.get("models", {}).get("primary", {})
        return primary.get("dimensions", 1024)

    @property
    def batch_size(self) -> int:
        primary = self._config.get("models", {}).get("primary", {})
        return primary.get("batch_size", 128)

    async def embed_texts(self, texts: list[str]) -> list[list[float]]:
        """Embed a list of texts, batching as needed.

        Returns a list of embedding vectors, one per input text.
        """
        primary = self._config.get("models", {}).get("primary", {})
        litellm_id = primary.get("litellm_id", "")
        batch_size = self.batch_size

        all_embeddings: list[list[float]] = []

        for i in range(0, len(texts), batch_size):
            batch = texts[i : i + batch_size]
            try:
                from litellm import aembedding

                response = await aembedding(model=litellm_id, input=batch)
                batch_embeddings = [item["embedding"] for item in response.data]
                all_embeddings.extend(batch_embeddings)
            except Exception as exc:
                logger.error("embedding_failed", model=litellm_id, batch_start=i, error=str(exc))
                # Return zero vectors as fallback
                dims = self.dimensions
                all_embeddings.extend([[0.0] * dims] * len(batch))

        return all_embeddings

    async def embed_query(self, query: str) -> list[float]:
        """Embed a single query string."""
        results = await self.embed_texts([query])
        return results[0] if results else [0.0] * self.dimensions
