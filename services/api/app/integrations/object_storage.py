from __future__ import annotations

import asyncio
import hashlib
from dataclasses import dataclass
from io import BytesIO
from typing import Protocol
from uuid import UUID

import boto3
from botocore.client import Config

from ..core.settings import Settings, get_settings


@dataclass(frozen=True, slots=True)
class StoredObject:
    bucket_name: str
    object_key: str
    storage_version_id: str
    etag: str | None
    sha256: str
    size_bytes: int
    media_type: str | None


class ObjectStorage(Protocol):
    async def put_bytes(
        self,
        *,
        tenant_id: UUID,
        object_key: str,
        content: bytes,
        media_type: str | None,
        metadata: dict[str, str] | None = None,
    ) -> StoredObject: ...

    async def get_bytes(self, *, object_key: str, version_id: str | None = None) -> bytes: ...

    async def delete_version(self, *, object_key: str, version_id: str | None) -> str: ...


class S3ObjectStorage:
    def __init__(self, settings: Settings | None = None) -> None:
        self.settings = settings or get_settings()
        self.bucket = self.settings.object_storage_bucket
        self.client = boto3.client(
            "s3",
            endpoint_url=self.settings.object_storage_endpoint,
            region_name=self.settings.object_storage_region,
            aws_access_key_id=self.settings.object_storage_access_key.get_secret_value(),
            aws_secret_access_key=self.settings.object_storage_secret_key.get_secret_value(),
            use_ssl=self.settings.object_storage_secure,
            config=Config(signature_version="s3v4"),
        )

    async def ensure_bucket(self) -> None:
        def _ensure() -> None:
            try:
                self.client.head_bucket(Bucket=self.bucket)
            except Exception:
                self.client.create_bucket(Bucket=self.bucket)
            self.client.put_bucket_versioning(
                Bucket=self.bucket,
                VersioningConfiguration={"Status": "Enabled"},
            )

        await asyncio.to_thread(_ensure)

    async def probe_bucket(self) -> tuple[bool, str]:
        """Check availability and versioning without mutating storage state."""
        def _probe() -> tuple[bool, str]:
            self.client.head_bucket(Bucket=self.bucket)
            response = self.client.get_bucket_versioning(Bucket=self.bucket)
            status = response.get("Status", "Disabled")
            return status == "Enabled", status

        return await asyncio.to_thread(_probe)

    async def put_bytes(
        self,
        *,
        tenant_id: UUID,
        object_key: str,
        content: bytes,
        media_type: str | None,
        metadata: dict[str, str] | None = None,
    ) -> StoredObject:
        digest = hashlib.sha256(content).hexdigest()
        safe_metadata = {"tenant-id": str(tenant_id), "sha256": digest, **(metadata or {})}

        def _put() -> dict:
            return self.client.put_object(
                Bucket=self.bucket,
                Key=object_key,
                Body=BytesIO(content),
                ContentLength=len(content),
                ContentType=media_type or "application/octet-stream",
                Metadata=safe_metadata,
            )

        response = await asyncio.to_thread(_put)
        return StoredObject(
            bucket_name=self.bucket,
            object_key=object_key,
            storage_version_id=response.get("VersionId") or response.get("ETag", "unversioned").strip('"'),
            etag=response.get("ETag", "").strip('"') or None,
            sha256=digest,
            size_bytes=len(content),
            media_type=media_type,
        )

    async def get_bytes(self, *, object_key: str, version_id: str | None = None) -> bytes:
        def _get() -> bytes:
            kwargs = {"Bucket": self.bucket, "Key": object_key}
            if version_id:
                kwargs["VersionId"] = version_id
            response = self.client.get_object(**kwargs)
            return response["Body"].read()

        return await asyncio.to_thread(_get)

    async def delete_version(self, *, object_key: str, version_id: str | None) -> str:
        """Delete the exact object version and return provider evidence.

        A version identifier is required for versioned production storage so a
        legal deletion cannot accidentally remove a different revision.
        """
        if not version_id:
            raise ValueError("An object-storage version identifier is required for physical deletion.")
        def _delete() -> dict:
            kwargs = {"Bucket": self.bucket, "Key": object_key}
            if version_id not in {"unversioned", "null"}:
                kwargs["VersionId"] = version_id
            return self.client.delete_object(**kwargs)
        response = await asyncio.to_thread(_delete)
        return str(response.get("VersionId") or version_id)


class InMemoryObjectStorage:
    """Deterministic object store used by unit tests and local service tests."""

    def __init__(self, bucket: str = "test-bucket") -> None:
        self.bucket = bucket
        self.objects: dict[tuple[str, str], bytes] = {}
        self.version_counters: dict[str, int] = {}

    async def put_bytes(
        self,
        *,
        tenant_id: UUID,
        object_key: str,
        content: bytes,
        media_type: str | None,
        metadata: dict[str, str] | None = None,
    ) -> StoredObject:
        digest = hashlib.sha256(content).hexdigest()
        next_version = self.version_counters.get(object_key, 0) + 1
        self.version_counters[object_key] = next_version
        version_id = f"memory-v{next_version}"
        self.objects[(object_key, version_id)] = content
        return StoredObject(
            bucket_name=self.bucket,
            object_key=object_key,
            storage_version_id=version_id,
            etag=digest,
            sha256=digest,
            size_bytes=len(content),
            media_type=media_type,
        )

    async def get_bytes(self, *, object_key: str, version_id: str | None = None) -> bytes:
        if version_id is None:
            version = self.version_counters[object_key]
            version_id = f"memory-v{version}"
        return self.objects[(object_key, version_id)]

    async def delete_version(self, *, object_key: str, version_id: str | None) -> str:
        if not version_id:
            raise ValueError("version_id is required")
        self.objects.pop((object_key, version_id), None)
        return version_id


def build_object_key(*, tenant_id: UUID, document_id: UUID, version_number: int, filename: str) -> str:
    safe_name = "".join(ch if ch.isalnum() or ch in {".", "-", "_"} else "_" for ch in filename)
    return f"tenants/{tenant_id}/documents/{document_id}/versions/{version_number}/{safe_name}"
