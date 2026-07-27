from __future__ import annotations

from functools import lru_cache

from .core.settings import get_settings
from .ingestion.embeddings import EmbeddingClient, OllamaEmbeddingClient
from .integrations.malware_scanner import ClamAVMalwareScanner, DisabledMalwareScanner, MalwareScanner
from .integrations.object_storage import ObjectStorage, S3ObjectStorage
from .integrations.qdrant import QdrantGateway


@lru_cache(maxsize=1)
def get_object_storage() -> ObjectStorage:
    return S3ObjectStorage()


@lru_cache(maxsize=1)
def get_qdrant_gateway() -> QdrantGateway:
    return QdrantGateway(get_settings())


@lru_cache(maxsize=1)
def get_embedding_client() -> EmbeddingClient:
    settings = get_settings()
    if settings.embedding_provider != "ollama":
        raise RuntimeError("v1.6 currently requires the governed Ollama embedding provider.")
    return OllamaEmbeddingClient(settings)


@lru_cache(maxsize=1)
def get_malware_scanner() -> MalwareScanner:
    settings = get_settings()
    if not settings.malware_scan_enabled:
        return DisabledMalwareScanner()
    return ClamAVMalwareScanner(settings)
