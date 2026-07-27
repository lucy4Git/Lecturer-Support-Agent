from __future__ import annotations

import time
from collections.abc import Awaitable, Callable
from typing import Any

import httpx

from .base import ProviderError


async def post_json(
    *,
    provider: str,
    url: str,
    headers: dict[str, str],
    body: dict[str, Any],
    timeout_seconds: int,
    client: httpx.AsyncClient | None = None,
) -> tuple[dict[str, Any], int, httpx.Headers]:
    owns_client = client is None
    session = client or httpx.AsyncClient(timeout=timeout_seconds, follow_redirects=True)
    started = time.perf_counter()
    try:
        response = await session.post(url, headers=headers, json=body)
        latency_ms = int((time.perf_counter() - started) * 1000)
        if response.status_code >= 400:
            detail = response.text[:500]
            raise ProviderError(provider, f"HTTP {response.status_code}: {detail}", code=f"http_{response.status_code}")
        return response.json(), latency_ms, response.headers
    except httpx.TimeoutException as exc:
        raise ProviderError(provider, "The provider request timed out.", code="timeout") from exc
    except httpx.HTTPError as exc:
        raise ProviderError(provider, "The provider could not be reached.", code="network_error") from exc
    except ValueError as exc:
        raise ProviderError(provider, "The provider returned invalid JSON.", code="invalid_json") from exc
    finally:
        if owns_client:
            await session.aclose()
