from __future__ import annotations

import hmac
from dataclasses import asdict

from fastapi import APIRouter, Header, HTTPException, status
from fastapi.responses import PlainTextResponse

from ..core.settings import get_settings
from ..observability.metrics import METRICS
from ..services.readiness import ReadinessService

router = APIRouter(tags=["health"])


@router.get("/health")
async def health() -> dict[str, str]:
    return {"status": "ok", "service": "lecturer-support-agent-api", "version": "2.5.0"}


@router.get("/ready")
async def ready() -> dict:
    results = await ReadinessService().run()
    healthy = all(item.healthy for item in results)
    if not healthy:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail={
                "status": "not_ready",
                "checks": [asdict(item) for item in results],
            },
        )
    return {
        "status": "ready",
        "version": "2.5.0",
        "checks": [asdict(item) for item in results],
    }


@router.get("/metrics", response_class=PlainTextResponse)
async def metrics(
    x_metrics_token: str | None = Header(default=None),
    authorization: str | None = Header(default=None),
) -> PlainTextResponse:
    settings = get_settings()
    if not settings.metrics_enabled:
        raise HTTPException(status_code=404, detail="Metrics are disabled.")
    if settings.metrics_token:
        expected = settings.metrics_token.get_secret_value()
        bearer = authorization.split(" ", 1)[1] if authorization and authorization.lower().startswith("bearer ") else None
        supplied = x_metrics_token or bearer
        if not supplied or not hmac.compare_digest(supplied, expected):
            raise HTTPException(status_code=403, detail="Metrics token is invalid.")
    return PlainTextResponse(METRICS.render(), media_type="text/plain; version=0.0.4")
