"""
Tests for environment-aware readiness probe diagnostics (F-009 security cleanup).

Production responses must not expose connection strings, hostnames, passwords,
stack traces or SQL text to unauthenticated callers.  Development responses may
include sanitised exception type information.  Full detail is always sent to the
structured server logger.
"""
from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from services.api.app.services.readiness import ProbeResult, ReadinessService


def _service(environment: str = "development") -> ReadinessService:
    settings = MagicMock()
    settings.environment = environment
    settings.readiness_probe_timeout_seconds = 5
    settings.readiness_require_ollama = False
    settings.qdrant_url = "http://localhost:6335"
    settings.ollama_base_url = "http://localhost:11434"
    return ReadinessService(settings=settings)


class TestSafeDetail:
    """_safe_detail must sanitise secrets regardless of environment."""

    def test_development_returns_exception_type(self) -> None:
        svc = _service("development")
        exc = RuntimeError("connection refused")
        detail = svc._safe_detail(exc, "abc12345")
        assert "RuntimeError" in detail

    def test_development_redacts_connection_string(self) -> None:
        svc = _service("development")
        exc = Exception("postgresql+psycopg://lsa_app:secret@localhost:5433/db")
        detail = svc._safe_detail(exc, "abc12345")
        assert "secret" not in detail
        assert "lsa_app" not in detail

    def test_production_returns_only_correlation_id(self) -> None:
        svc = _service("production")
        exc = RuntimeError("postgresql+psycopg://lsa_app:supersecret@db.internal:5432/prod")
        detail = svc._safe_detail(exc, "deadbeef")
        assert "supersecret" not in detail
        assert "db.internal" not in detail
        assert "lsa_app" not in detail
        assert "deadbeef" in detail
        assert "dependency_unavailable" in detail

    def test_production_redacts_exception_type(self) -> None:
        svc = _service("production")
        exc = ValueError("InterfaceError: ProactorEventLoop")
        detail = svc._safe_detail(exc, "abc12345")
        # Exception type and message must NOT appear in production detail
        assert "ValueError" not in detail
        assert "InterfaceError" not in detail
        assert "ProactorEventLoop" not in detail

    def test_production_does_not_expose_redis_url(self) -> None:
        svc = _service("production")
        exc = ConnectionError("redis://:password@localhost:6380/0")
        detail = svc._safe_detail(exc, "abc12345")
        assert "password" not in detail
        assert "redis://" not in detail

    def test_staging_treated_as_production(self) -> None:
        svc = _service("staging")
        exc = RuntimeError("some internal detail")
        detail = svc._safe_detail(exc, "abc12345")
        assert "some internal detail" not in detail
        assert "dependency_unavailable" in detail

    def test_test_environment_treated_as_development(self) -> None:
        svc = _service("test")
        exc = RuntimeError("connection refused")
        detail = svc._safe_detail(exc, "abc12345")
        assert "RuntimeError" in detail


class TestRunReturnsProbeResults:
    """run() must return one ProbeResult per probe with safe details on failure."""

    @pytest.mark.asyncio
    async def test_production_failure_detail_is_safe(self) -> None:
        svc = _service("production")
        error = Exception("postgresql+psycopg://lsa_app:supersecret@db.internal:5432/prod")

        async def _bad_db() -> ProbeResult:
            raise error

        async def _ok_redis() -> ProbeResult:
            return ProbeResult("redis", True, "reachable")

        async def _ok_qdrant() -> ProbeResult:
            return ProbeResult("qdrant", True, "reachable")

        async def _ok_storage() -> ProbeResult:
            return ProbeResult("object_storage", True, "bucket_available_and_versioned")

        with (
            patch.object(svc, "_database", _bad_db),
            patch.object(svc, "_redis", _ok_redis),
            patch.object(svc, "_qdrant", _ok_qdrant),
            patch.object(svc, "_object_storage", _ok_storage),
        ):
            results = await svc.run()

        pg = next(r for r in results if r.name == "postgresql")
        assert not pg.healthy
        assert "supersecret" not in pg.detail
        assert "db.internal" not in pg.detail
        assert "dependency_unavailable" in pg.detail

    @pytest.mark.asyncio
    async def test_all_healthy_returns_correct_results(self) -> None:
        svc = _service("production")

        async def _ok() -> ProbeResult:
            return ProbeResult("postgresql", True, "reachable")

        async def _ok_redis() -> ProbeResult:
            return ProbeResult("redis", True, "reachable")

        async def _ok_qdrant() -> ProbeResult:
            return ProbeResult("qdrant", True, "reachable")

        async def _ok_storage() -> ProbeResult:
            return ProbeResult("object_storage", True, "bucket_available_and_versioned")

        with (
            patch.object(svc, "_database", _ok),
            patch.object(svc, "_redis", _ok_redis),
            patch.object(svc, "_qdrant", _ok_qdrant),
            patch.object(svc, "_object_storage", _ok_storage),
        ):
            results = await svc.run()

        assert all(r.healthy for r in results)
        assert len(results) == 4
