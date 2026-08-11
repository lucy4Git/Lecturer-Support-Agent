from __future__ import annotations

import asyncio
import logging
import uuid
from dataclasses import dataclass
from typing import Awaitable, Callable

import httpx
from sqlalchemy import text

from ..core.database import get_application_engine
from ..core.settings import Settings, get_settings
from ..integrations.object_storage import S3ObjectStorage

logger = logging.getLogger(__name__)


@dataclass(frozen=True, slots=True)
class ProbeResult:
    name: str
    healthy: bool
    detail: str


class ReadinessService:
    def __init__(self, settings: Settings | None = None) -> None:
        self.settings = settings or get_settings()

    @property
    def _is_development(self) -> bool:
        return self.settings.environment.lower() in ("development", "test", "local")

    def _safe_detail(self, exc: Exception, correlation_id: str, *, probe: str = "unknown") -> str:
        """Return a safe probe-failure detail suitable for unauthenticated clients.

        Development: full exception type and sanitised message (no connection
        strings, passwords, host names or tokens).
        Production: only the dependency name and a correlation identifier so that
        operators can correlate against structured server logs.
        """
        if self._is_development:
            # Strip connection strings and passwords from the message
            raw = str(exc)
            for secret in (
                "password", "postgresql+psycopg://", "redis://", "http://",
                "https://", "@localhost", "@127",
            ):
                if secret in raw.lower():
                    raw = "<detail redacted — connection string>"
                    break
            return f"{type(exc).__name__}: {raw}"[:300]
        # Production: log full detail server-side, return only correlation id
        logger.error(
            "Readiness probe failure",
            extra={
                "probe": probe,
                "exc_type": type(exc).__name__,
                "exc_detail": str(exc),
                "correlation_id": correlation_id,
            },
        )
        return f"dependency_unavailable [ref:{correlation_id}]"

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
        url = (
            f"{self.settings.qdrant_url.rstrip('/')}"
            f"/collections/{self.settings.qdrant_collection}"
        )
        headers: dict[str, str] = {}
        if self.settings.qdrant_api_key:
            headers["api-key"] = self.settings.qdrant_api_key.get_secret_value()
        async with httpx.AsyncClient(timeout=self.settings.readiness_probe_timeout_seconds) as client:
            response = await client.get(url, headers=headers)
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
            correlation_id = str(uuid.uuid4())[:8]
            try:
                results.append(await asyncio.wait_for(
                    probe(), timeout=self.settings.readiness_probe_timeout_seconds
                ))
            except Exception as exc:
                logger.warning(
                    "Readiness probe failed",
                    extra={"probe": name, "exc_type": type(exc).__name__, "correlation_id": correlation_id},
                )
                results.append(ProbeResult(name, False, self._safe_detail(exc, correlation_id, probe=name)))
        return results
