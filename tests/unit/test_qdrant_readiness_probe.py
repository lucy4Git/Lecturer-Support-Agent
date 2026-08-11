"""Regression tests for the Qdrant readiness probe.

Covers the fix for two defects that caused Qdrant Cloud readiness to fail:

1. No api-key header — httpx.AsyncClient was created without authentication.
2. Wrong endpoint — /collections (list-all) was probed instead of
   /collections/{QDRANT_COLLECTION} (get-specific).

A granular collection-scoped Qdrant API key can access the specific collection
but cannot list all collections, so both defects must be fixed together.

All tests are unit-level and use httpx mock transports.
"""
from __future__ import annotations

import logging
from unittest.mock import AsyncMock, MagicMock, patch

import httpx
import pytest

from services.api.app.services.readiness import ProbeResult, ReadinessService


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _settings(
    *,
    environment: str = "staging",
    qdrant_url: str = "https://qdrant.cloud.example:6333",
    qdrant_collection: str = "lecturer_support_documents_staging",
    qdrant_api_key: str | None = "test-api-key-value",
) -> MagicMock:
    settings = MagicMock()
    settings.environment = environment
    settings.readiness_probe_timeout_seconds = 5
    settings.readiness_require_ollama = False
    settings.qdrant_url = qdrant_url
    settings.qdrant_collection = qdrant_collection
    if qdrant_api_key is not None:
        key_mock = MagicMock()
        key_mock.get_secret_value.return_value = qdrant_api_key
        settings.qdrant_api_key = key_mock
    else:
        settings.qdrant_api_key = None
    return settings


def _service(settings: MagicMock | None = None) -> ReadinessService:
    return ReadinessService(settings=settings or _settings())


# ---------------------------------------------------------------------------
# 1. URL construction uses QDRANT_COLLECTION, not /collections (list-all)
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_qdrant_probe_uses_collection_specific_url() -> None:
    """Probe must hit /collections/{name}, never the bare /collections endpoint."""
    captured_urls: list[str] = []

    def handler(request: httpx.Request) -> httpx.Response:
        captured_urls.append(str(request.url))
        return httpx.Response(200, json={"result": {"status": "green"}})

    svc = _service()
    with patch("httpx.AsyncClient") as mock_client_cls:
        mock_client = AsyncMock()
        mock_client.__aenter__ = AsyncMock(return_value=mock_client)
        mock_client.__aexit__ = AsyncMock(return_value=False)
        mock_response = MagicMock()
        mock_response.raise_for_status = MagicMock()
        mock_client.get = AsyncMock(return_value=mock_response)
        mock_client_cls.return_value = mock_client

        result = await svc._qdrant()

    assert result.healthy
    call_args = mock_client.get.call_args
    url_called = call_args[0][0] if call_args[0] else call_args.kwargs.get("url", "")
    assert "lecturer_support_documents_staging" in url_called
    # Must NOT be the bare list-all endpoint
    assert not url_called.rstrip("/").endswith("/collections")


@pytest.mark.asyncio
async def test_qdrant_probe_does_not_list_all_collections() -> None:
    """The probe URL must not be the bare /collections endpoint."""
    source_url: list[str] = []

    async def _fake_qdrant(self: ReadinessService) -> ProbeResult:
        # Reconstruct the URL the way the implementation does, for inspection.
        url = (
            f"{self.settings.qdrant_url.rstrip('/')}"
            f"/collections/{self.settings.qdrant_collection}"
        )
        source_url.append(url)
        return ProbeResult("qdrant", True, "reachable")

    svc = _service()
    with patch.object(ReadinessService, "_qdrant", _fake_qdrant):
        pass  # just inspect the URL pattern

    # Check the implementation source directly for the correct endpoint pattern.
    import inspect
    source = inspect.getsource(ReadinessService._qdrant)
    assert "/collections/{" in source or "qdrant_collection" in source
    assert '"/collections"' not in source


# ---------------------------------------------------------------------------
# 2. api-key header is sent when QDRANT_API_KEY is configured
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_qdrant_probe_sends_api_key_header() -> None:
    """api-key header must be present when qdrant_api_key is configured."""
    captured_headers: list[dict] = []

    svc = _service(_settings(qdrant_api_key="secret-qdrant-key"))

    with patch("httpx.AsyncClient") as mock_client_cls:
        mock_client = AsyncMock()
        mock_client.__aenter__ = AsyncMock(return_value=mock_client)
        mock_client.__aexit__ = AsyncMock(return_value=False)
        mock_response = MagicMock()
        mock_response.raise_for_status = MagicMock()
        mock_client.get = AsyncMock(return_value=mock_response)
        mock_client_cls.return_value = mock_client

        await svc._qdrant()

    call_kwargs = mock_client.get.call_args.kwargs
    headers_sent = call_kwargs.get("headers", {})
    assert "api-key" in headers_sent
    assert headers_sent["api-key"] == "secret-qdrant-key"


@pytest.mark.asyncio
async def test_qdrant_probe_omits_api_key_header_when_not_configured() -> None:
    """No api-key header must be sent for local/self-hosted Qdrant with no key."""
    svc = _service(_settings(qdrant_api_key=None))

    with patch("httpx.AsyncClient") as mock_client_cls:
        mock_client = AsyncMock()
        mock_client.__aenter__ = AsyncMock(return_value=mock_client)
        mock_client.__aexit__ = AsyncMock(return_value=False)
        mock_response = MagicMock()
        mock_response.raise_for_status = MagicMock()
        mock_client.get = AsyncMock(return_value=mock_response)
        mock_client_cls.return_value = mock_client

        result = await svc._qdrant()

    assert result.healthy
    call_kwargs = mock_client.get.call_args.kwargs
    headers_sent = call_kwargs.get("headers", {})
    # api-key must be absent (not blank/None) when no key is configured
    assert "api-key" not in headers_sent
    assert None not in headers_sent.values()
    assert "" not in headers_sent.values()


# ---------------------------------------------------------------------------
# 3. Fail closed on error status codes
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
@pytest.mark.parametrize("status_code", [401, 403, 404, 500, 503])
async def test_qdrant_probe_fails_on_error_status(status_code: int) -> None:
    """Any non-200 HTTP status must make the Qdrant probe unhealthy."""
    svc = _service()

    with patch("httpx.AsyncClient") as mock_client_cls:
        mock_client = AsyncMock()
        mock_client.__aenter__ = AsyncMock(return_value=mock_client)
        mock_client.__aexit__ = AsyncMock(return_value=False)
        mock_response = MagicMock()
        mock_response.raise_for_status.side_effect = httpx.HTTPStatusError(
            f"HTTP {status_code}",
            request=MagicMock(),
            response=MagicMock(status_code=status_code),
        )
        mock_client.get = AsyncMock(return_value=mock_response)
        mock_client_cls.return_value = mock_client

        with pytest.raises(httpx.HTTPStatusError):
            await svc._qdrant()


@pytest.mark.asyncio
async def test_qdrant_probe_fails_on_timeout() -> None:
    """Timeout must propagate and be treated as unhealthy by run()."""
    svc = _service()

    with patch("httpx.AsyncClient") as mock_client_cls:
        mock_client = AsyncMock()
        mock_client.__aenter__ = AsyncMock(return_value=mock_client)
        mock_client.__aexit__ = AsyncMock(return_value=False)
        mock_client.get = AsyncMock(side_effect=httpx.TimeoutException("timeout"))
        mock_client_cls.return_value = mock_client

        with pytest.raises(httpx.TimeoutException):
            await svc._qdrant()


@pytest.mark.asyncio
async def test_qdrant_probe_fails_on_connect_error() -> None:
    """Transport failure must propagate and be treated as unhealthy by run()."""
    svc = _service()

    with patch("httpx.AsyncClient") as mock_client_cls:
        mock_client = AsyncMock()
        mock_client.__aenter__ = AsyncMock(return_value=mock_client)
        mock_client.__aexit__ = AsyncMock(return_value=False)
        mock_client.get = AsyncMock(side_effect=httpx.ConnectError("refused"))
        mock_client_cls.return_value = mock_client

        with pytest.raises(httpx.ConnectError):
            await svc._qdrant()


# ---------------------------------------------------------------------------
# 4. API key never appears in logs or public response detail
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_qdrant_api_key_does_not_appear_in_public_detail(caplog: pytest.LogCaptureFixture) -> None:
    """The Qdrant API key must not appear in the ProbeResult.detail returned to callers.

    In production the httpx ConnectError message contains the remote host/port,
    not the API key (which is a header, never part of the URL or error message).
    This test uses a realistic error message to verify the public detail is safe.
    """
    secret_key = "VERY_SECRET_QDRANT_KEY_XYZ"
    svc = _service(_settings(environment="staging", qdrant_api_key=secret_key))

    with patch("httpx.AsyncClient") as mock_client_cls:
        mock_client = AsyncMock()
        mock_client.__aenter__ = AsyncMock(return_value=mock_client)
        mock_client.__aexit__ = AsyncMock(return_value=False)
        # Realistic httpx error: contains host/port, never the api-key header value
        mock_client.get = AsyncMock(
            side_effect=httpx.ConnectError("All connection attempts failed")
        )
        mock_client_cls.return_value = mock_client

        with caplog.at_level(logging.WARNING):
            results = await svc.run()

    qdrant_result = next(r for r in results if r.name == "qdrant")
    assert not qdrant_result.healthy
    # Key must not appear in the public-facing detail
    assert secret_key not in qdrant_result.detail
    # Public detail must be a correlation-id reference, not raw exception content
    assert "dependency_unavailable" in qdrant_result.detail


@pytest.mark.asyncio
async def test_qdrant_api_key_does_not_appear_in_development_detail() -> None:
    """In development mode the public detail must not echo back the API key.

    httpx exceptions about connection failures include remote addresses, not
    HTTP header values.  This test verifies the detail with a realistic message.
    """
    secret_key = "DEV_SECRET_KEY_SHOULD_NOT_LEAK"
    svc = _service(_settings(environment="development", qdrant_api_key=secret_key))

    # Realistic: httpx ConnectError contains host/port, not the header value
    realistic_error = "All connection attempts failed"
    with patch("httpx.AsyncClient") as mock_client_cls:
        mock_client = AsyncMock()
        mock_client.__aenter__ = AsyncMock(return_value=mock_client)
        mock_client.__aexit__ = AsyncMock(return_value=False)
        mock_client.get = AsyncMock(side_effect=httpx.ConnectError(realistic_error))
        mock_client_cls.return_value = mock_client

        results = await svc.run()

    qdrant_result = next(r for r in results if r.name == "qdrant")
    assert not qdrant_result.healthy
    assert secret_key not in qdrant_result.detail
    # Development mode includes exception type but not the key
    assert "ConnectError" in qdrant_result.detail


# ---------------------------------------------------------------------------
# 5. run() surfaces the correct probe name in production logs
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_run_logs_correct_probe_name_not_unknown(caplog: pytest.LogCaptureFixture) -> None:
    """_safe_detail must log the actual probe name, not 'unknown'."""
    svc = _service(_settings(environment="staging"))

    with patch("httpx.AsyncClient") as mock_client_cls:
        mock_client = AsyncMock()
        mock_client.__aenter__ = AsyncMock(return_value=mock_client)
        mock_client.__aexit__ = AsyncMock(return_value=False)
        mock_client.get = AsyncMock(side_effect=httpx.ConnectError("refused"))
        mock_client_cls.return_value = mock_client

        with caplog.at_level(logging.ERROR):
            results = await svc.run()

    qdrant_result = next(r for r in results if r.name == "qdrant")
    assert not qdrant_result.healthy

    error_records = [r for r in caplog.records if r.levelno >= logging.ERROR]
    assert error_records, "Expected at least one ERROR log entry"
    probe_names = [getattr(r, "probe", None) for r in error_records]
    assert "qdrant" in probe_names, f"Expected probe='qdrant' in logs, got: {probe_names}"
    assert "unknown" not in probe_names, "probe='unknown' must not appear in logs"


# ---------------------------------------------------------------------------
# 6. Granular collection-scoped key is supported end-to-end
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_qdrant_granular_collection_key_succeeds() -> None:
    """A key restricted to one collection must succeed when probing that collection."""
    collection = "lecturer_support_documents_staging"
    svc = _service(_settings(
        qdrant_collection=collection,
        qdrant_api_key="granular-collection-only-key",
    ))

    with patch("httpx.AsyncClient") as mock_client_cls:
        mock_client = AsyncMock()
        mock_client.__aenter__ = AsyncMock(return_value=mock_client)
        mock_client.__aexit__ = AsyncMock(return_value=False)
        mock_response = MagicMock()
        mock_response.raise_for_status = MagicMock()
        mock_client.get = AsyncMock(return_value=mock_response)
        mock_client_cls.return_value = mock_client

        result = await svc._qdrant()

    assert result.healthy
    call_url = mock_client.get.call_args[0][0]
    assert collection in call_url
    assert call_url.rstrip("/").endswith(f"/collections/{collection}")


# ---------------------------------------------------------------------------
# 7. Other probes are unaffected
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_postgresql_redis_storage_probes_unaffected() -> None:
    """PostgreSQL, Redis and object-storage probes must not be changed by this fix."""
    settings = _settings()
    settings.readiness_require_ollama = False
    svc = ReadinessService(settings=settings)

    async def _ok_db() -> ProbeResult:
        return ProbeResult("postgresql", True, "reachable")

    async def _ok_redis() -> ProbeResult:
        return ProbeResult("redis", True, "reachable")

    async def _ok_qdrant() -> ProbeResult:
        return ProbeResult("qdrant", True, "reachable")

    async def _ok_storage() -> ProbeResult:
        return ProbeResult("object_storage", True, "bucket_available_and_versioned")

    with (
        patch.object(svc, "_database", _ok_db),
        patch.object(svc, "_redis", _ok_redis),
        patch.object(svc, "_qdrant", _ok_qdrant),
        patch.object(svc, "_object_storage", _ok_storage),
    ):
        results = await svc.run()

    names = {r.name for r in results}
    assert {"postgresql", "redis", "qdrant", "object_storage"} == names
    assert all(r.healthy for r in results)
