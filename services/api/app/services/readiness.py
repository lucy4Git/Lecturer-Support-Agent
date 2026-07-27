from __future__ import annotations

import asyncio
from dataclasses import dataclass
from typing import Awaitable, Callable

import httpx
from sqlalchemy import text

from ..core.database import get_application_engine
from ..core.settings import Settings, get_settings
from ..integrations.object_storage import S3ObjectStorage


@dataclass(frozen=True, slots=True)
class ProbeResult:
    name: str
    healthy: bool
    detail: str


class ReadinessService:
    def __init__(self, settings: Settings | None = None) -> None:
        self.settings = settings or get_settings()

    async def _database(self) -> ProbeResult:
        async with get_application_engine().connect() as connection:
            await connection.execute(text("SELECT 1"))
        return ProbeResult("postgresql", True, "reachable")

    async def _redis(self) -> ProbeResult:
        from ..integrations.redis_gateway import RedisGateway
        gateway = RedisGateway(self.settings)
        try:
            await gateway.ping()
        finally:
            await gateway.close()
        return ProbeResult("redis", True, "reachable")

    async def _qdrant(self) -> ProbeResult:
        async with httpx.AsyncClient(timeout=self.settings.readiness_probe_timeout_seconds) as client:
            response = await client.get(f"{self.settings.qdrant_url.rstrip('/')}/collections")
            response.raise_for_status()
        return ProbeResult("qdrant", True, "reachable")

    async def _ollama(self) -> ProbeResult:
        async with httpx.AsyncClient(timeout=self.settings.readiness_probe_timeout_seconds) as client:
            response = await client.get(f"{self.settings.ollama_base_url.rstrip('/')}/api/tags")
            response.raise_for_status()
        return ProbeResult("ollama", True, "reachable")

    async def _object_storage(self) -> ProbeResult:
        storage = S3ObjectStorage(self.settings)
        enabled, status = await storage.probe_bucket()
        if not enabled:
            raise RuntimeError(f"Object-storage bucket versioning is {status}.")
        return ProbeResult("object_storage", True, "bucket_available_and_versioned")

    async def run(self) -> list[ProbeResult]:
        probes: list[tuple[str, Callable[[], Awaitable[ProbeResult]]]] = [
            ("postgresql", self._database), ("redis", self._redis),
            ("qdrant", self._qdrant), ("object_storage", self._object_storage),
        ]
        if self.settings.readiness_require_ollama:
            probes.append(("ollama", self._ollama))
        results: list[ProbeResult] = []
        for name, probe in probes:
            try:
                results.append(await asyncio.wait_for(probe(), timeout=self.settings.readiness_probe_timeout_seconds))
            except Exception as exc:
                results.append(ProbeResult(name, False, type(exc).__name__))
        return results
