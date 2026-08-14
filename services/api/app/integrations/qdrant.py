from __future__ import annotations

from dataclasses import dataclass
from typing import Any
from uuid import UUID

import httpx

from ..core.settings import Settings, get_settings


@dataclass(frozen=True, slots=True)
class RetrievalScope:
    tenant_id: UUID
    user_id: UUID
    allowed_org_unit_ids: tuple[UUID, ...] = ()
    allowed_programme_ids: tuple[UUID, ...] = ()
    allowed_module_ids: tuple[UUID, ...] = ()
    include_public: bool = True


def build_tenant_filter(scope: RetrievalScope) -> dict[str, Any]:
    scoped_should: list[dict[str, Any]] = []
    for key, values in (
        ("org_unit_id", scope.allowed_org_unit_ids),
        ("programme_id", scope.allowed_programme_ids),
        ("module_id", scope.allowed_module_ids),
    ):
        if values:
            scoped_should.append({"key": key, "match": {"any": [str(value) for value in values]}})
    scoped_should.append({"key": "owner_user_id", "match": {"value": str(scope.user_id)}})
    scoped_should.append({"key": "visibility", "match": {"value": "institution"}})

    # Qdrant requires `should` at the same level as `must`, not nested inside `must`.
    # When both `must` and `should` are present, all `must` conditions AND at least one
    # `should` condition must match.
    tenant_branch: dict[str, Any] = {
        "must": [
            {"key": "tenant_id", "match": {"value": str(scope.tenant_id)}},
            {"key": "is_deleted", "match": {"value": False}},
            {"key": "is_current", "match": {"value": True}},
        ],
        "should": scoped_should,
    }
    if not scope.include_public:
        return tenant_branch
    # For include_public: tenant-scoped docs OR globally public docs.
    # Qdrant nested conditions in `should` are plain filter objects (no wrapper).
    return {
        "should": [
            tenant_branch,
            {
                "must": [
                    {"key": "visibility", "match": {"value": "public"}},
                    {"key": "is_deleted", "match": {"value": False}},
                ]
            },
        ],
    }


class QdrantGateway:
    def __init__(self, settings: Settings | None = None, client: httpx.AsyncClient | None = None) -> None:
        self.settings = settings or get_settings()
        headers = {}
        if self.settings.qdrant_api_key:
            headers["api-key"] = self.settings.qdrant_api_key.get_secret_value()
        self.client = client or httpx.AsyncClient(
            base_url=self.settings.qdrant_url, headers=headers, timeout=30
        )
        self._owns_client = client is None

    async def close(self) -> None:
        if self._owns_client:
            await self.client.aclose()

    async def ensure_collection(self, *, vector_size: int) -> None:
        response = await self.client.get(f"/collections/{self.settings.qdrant_collection}")
        if response.status_code == 404:
            created = await self.client.put(
                f"/collections/{self.settings.qdrant_collection}",
                json={
                    "vectors": {"default": {"size": vector_size, "distance": "Cosine"}},
                    "on_disk_payload": True,
                },
            )
            created.raise_for_status()
            return
        response.raise_for_status()
        configured = (
            response.json().get("result", {}).get("config", {}).get("params", {}).get("vectors", {})
        )
        if isinstance(configured, dict) and "default" in configured:
            actual = configured["default"].get("size")
            if actual and int(actual) != vector_size:
                raise ValueError(
                    f"Qdrant collection dimension {actual} does not match embedding dimension {vector_size}."
                )

    async def upsert_points(self, points: list[dict[str, Any]]) -> None:
        if not points:
            return
        response = await self.client.put(
            f"/collections/{self.settings.qdrant_collection}/points",
            json={"points": points, "wait": True},
        )
        response.raise_for_status()

    async def delete_document_version(self, *, tenant_id: UUID, document_version_id: UUID) -> None:
        response = await self.client.post(
            f"/collections/{self.settings.qdrant_collection}/points/delete",
            json={
                "filter": {
                    "must": [
                        {"key": "tenant_id", "match": {"value": str(tenant_id)}},
                        {"key": "document_version_id", "match": {"value": str(document_version_id)}},
                    ]
                },
                "wait": True,
            },
        )
        if response.status_code != 404:
            response.raise_for_status()

    async def search(
        self,
        *,
        vector: list[float],
        scope: RetrievalScope,
        limit: int = 10,
        score_threshold: float | None = None,
    ) -> list[dict[str, Any]]:
        body: dict[str, Any] = {
            "vector": {"name": "default", "vector": vector},
            "filter": build_tenant_filter(scope),
            "limit": limit,
            "with_payload": True,
        }
        if score_threshold is not None:
            body["score_threshold"] = score_threshold
        response = await self.client.post(
            f"/collections/{self.settings.qdrant_collection}/points/search", json=body
        )
        response.raise_for_status()
        return response.json().get("result", [])
