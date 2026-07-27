from __future__ import annotations

import hashlib
import math
from typing import Protocol

import httpx

from ..core.settings import Settings, get_settings


class EmbeddingClient(Protocol):
    provider_name: str
    model_name: str
    dimension: int

    async def embed(self, texts: list[str]) -> list[list[float]]: ...


class OllamaEmbeddingClient:
    provider_name = "ollama"

    def __init__(self, settings: Settings | None = None, client: httpx.AsyncClient | None = None) -> None:
        self.settings = settings or get_settings()
        self.model_name = self.settings.ollama_embedding_model
        self.dimension = self.settings.embedding_dimension
        self.client = client or httpx.AsyncClient(
            base_url=self.settings.ollama_base_url,
            timeout=self.settings.embedding_timeout_seconds,
        )
        self._owns_client = client is None

    async def close(self) -> None:
        if self._owns_client:
            await self.client.aclose()

    async def embed(self, texts: list[str]) -> list[list[float]]:
        if not texts:
            return []
        response = await self.client.post("/api/embed", json={"model": self.model_name, "input": texts})
        response.raise_for_status()
        payload = response.json()
        vectors = payload.get("embeddings")
        if not isinstance(vectors, list) or len(vectors) != len(texts):
            raise ValueError("Ollama returned an invalid embeddings response.")
        for vector in vectors:
            if len(vector) != self.dimension:
                raise ValueError(
                    f"Embedding dimension {len(vector)} does not match configured Qdrant dimension {self.dimension}."
                )
        return vectors


class DeterministicEmbeddingClient:
    """Stable test-only embedding client; it is not a semantic production model."""

    provider_name = "deterministic_test"
    model_name = "sha256-projection-v1"

    def __init__(self, dimension: int = 32) -> None:
        self.dimension = dimension

    async def embed(self, texts: list[str]) -> list[list[float]]:
        output: list[list[float]] = []
        for text in texts:
            seed = hashlib.sha256(text.encode("utf-8")).digest()
            raw = [(seed[index % len(seed)] / 127.5) - 1.0 for index in range(self.dimension)]
            norm = math.sqrt(sum(value * value for value in raw)) or 1.0
            output.append([value / norm for value in raw])
        return output
