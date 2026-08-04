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


class _HTTPEmbeddingClient:
    provider_name = "http"

    def __init__(self, *, settings: Settings, client: httpx.AsyncClient | None = None) -> None:
        self.settings = settings
        self.dimension = settings.embedding_dimension
        self.client = client or httpx.AsyncClient(timeout=settings.embedding_timeout_seconds)
        self._owns_client = client is None

    async def close(self) -> None:
        if self._owns_client:
            await self.client.aclose()

    def _validate(self, vectors: object, expected: int) -> list[list[float]]:
        if not isinstance(vectors, list) or len(vectors) != expected:
            raise ValueError(f"{self.provider_name} returned an invalid embeddings response.")
        output: list[list[float]] = []
        for vector in vectors:
            if not isinstance(vector, list) or len(vector) != self.dimension:
                length = len(vector) if isinstance(vector, list) else "invalid"
                raise ValueError(
                    f"Embedding dimension {length} does not match configured Qdrant dimension "
                    f"{self.dimension}."
                )
            values = [float(value) for value in vector]
            if not all(math.isfinite(value) for value in values):
                raise ValueError(f"{self.provider_name} returned a non-finite embedding value.")
            output.append(values)
        return output


class OllamaEmbeddingClient(_HTTPEmbeddingClient):
    provider_name = "ollama"

    def __init__(self, settings: Settings | None = None, client: httpx.AsyncClient | None = None) -> None:
        resolved = settings or get_settings()
        super().__init__(settings=resolved, client=client or httpx.AsyncClient(
            base_url=resolved.ollama_base_url,
            timeout=resolved.embedding_timeout_seconds,
        ))
        self._owns_client = client is None
        self.model_name = resolved.ollama_embedding_model

    async def embed(self, texts: list[str]) -> list[list[float]]:
        if not texts:
            return []
        response = await self.client.post("/api/embed", json={"model": self.model_name, "input": texts})
        response.raise_for_status()
        return self._validate(response.json().get("embeddings"), len(texts))


class GeminiEmbeddingClient(_HTTPEmbeddingClient):
    """Google Gemini embedding adapter for hosted deployments.

    It uses the public REST batch embedding endpoint and keeps the API key in an
    HTTP header. The configured output dimensionality must match Qdrant.
    """

    provider_name = "google_gemini"

    def __init__(self, settings: Settings | None = None, client: httpx.AsyncClient | None = None) -> None:
        resolved = settings or get_settings()
        super().__init__(settings=resolved, client=client)
        self.model_name = resolved.google_gemini_embedding_model
        self.base_url = resolved.google_gemini_base_url.rstrip("/")
        self.api_key = resolved.google_gemini_api_key

    async def embed(self, texts: list[str]) -> list[list[float]]:
        if not texts:
            return []
        if self.api_key is None or not self.api_key.get_secret_value():
            raise RuntimeError("GOOGLE_GEMINI_API_KEY is required for Gemini embeddings.")
        model = self.model_name.removeprefix("models/")
        requests = [
            {
                "model": f"models/{model}",
                "content": {"parts": [{"text": text}]},
                "outputDimensionality": self.dimension,
                "taskType": "RETRIEVAL_DOCUMENT",
            }
            for text in texts
        ]
        response = await self.client.post(
            f"{self.base_url}/v1beta/models/{model}:batchEmbedContents",
            headers={"x-goog-api-key": self.api_key.get_secret_value()},
            json={"requests": requests},
        )
        response.raise_for_status()
        items = response.json().get("embeddings")
        vectors = [item.get("values") for item in items] if isinstance(items, list) else items
        return self._validate(vectors, len(texts))


class OpenAIEmbeddingClient(_HTTPEmbeddingClient):
    provider_name = "openai"

    def __init__(self, settings: Settings | None = None, client: httpx.AsyncClient | None = None) -> None:
        resolved = settings or get_settings()
        super().__init__(settings=resolved, client=client)
        self.model_name = resolved.openai_embedding_model
        self.base_url = resolved.openai_base_url.rstrip("/")
        self.api_key = resolved.openai_api_key

    async def embed(self, texts: list[str]) -> list[list[float]]:
        if not texts:
            return []
        if self.api_key is None or not self.api_key.get_secret_value():
            raise RuntimeError("OPENAI_API_KEY is required for OpenAI embeddings.")
        response = await self.client.post(
            f"{self.base_url}/embeddings",
            headers={"Authorization": f"Bearer {self.api_key.get_secret_value()}"},
            json={"model": self.model_name, "input": texts, "dimensions": self.dimension},
        )
        response.raise_for_status()
        data = response.json().get("data")
        if not isinstance(data, list):
            return self._validate(data, len(texts))
        ordered = sorted(data, key=lambda item: int(item.get("index", 0)))
        return self._validate([item.get("embedding") for item in ordered], len(texts))


def build_embedding_client(
    settings: Settings | None = None,
    *,
    client: httpx.AsyncClient | None = None,
) -> EmbeddingClient:
    resolved = settings or get_settings()
    provider = resolved.embedding_provider.strip().lower()
    if provider == "ollama":
        return OllamaEmbeddingClient(resolved, client)
    if provider in {"gemini", "google_gemini"}:
        return GeminiEmbeddingClient(resolved, client)
    if provider == "openai":
        return OpenAIEmbeddingClient(resolved, client)
    raise RuntimeError(
        "EMBEDDING_PROVIDER must be one of: ollama, google_gemini, openai."
    )


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
