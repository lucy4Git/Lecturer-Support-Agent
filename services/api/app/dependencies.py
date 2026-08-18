from __future__ import annotations

from functools import lru_cache

from .core.settings import get_settings
from .ingestion.embeddings import EmbeddingClient, build_embedding_client
from .integrations.malware_scanner import (
    ClamAVMalwareScanner,
    CloudmersiveMalwareScanner,
    DisabledMalwareScanner,
    MalwareScanner,
)
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
    return build_embedding_client(get_settings())


@lru_cache(maxsize=1)
def get_malware_scanner() -> MalwareScanner:
    settings = get_settings()
    if not settings.malware_scan_enabled:
        return DisabledMalwareScanner()
    provider = settings.malware_scanner_provider.lower().strip()
    if provider == "cloudmersive":
        return CloudmersiveMalwareScanner(settings)
    if provider == "clamav":
        return ClamAVMalwareScanner(settings)
    raise ValueError(
        f"Unknown MALWARE_SCANNER_PROVIDER '{provider}'. Allowed values: clamav, cloudmersive."
    )
