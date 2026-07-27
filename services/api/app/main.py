from __future__ import annotations

from fastapi import FastAPI, Request, status
from fastapi.responses import JSONResponse
from fastapi.middleware.cors import CORSMiddleware
from starlette.middleware.trustedhost import TrustedHostMiddleware

from .ai.providers import ProviderError

from .core.hardening import RateLimitMiddleware, RequestMetricsMiddleware, RequestSizeLimitMiddleware, SecurityHeadersMiddleware
from .core.middleware import RequestContextMiddleware
from .observability.logging import configure_logging
from .core.settings import get_settings
from .routes import (
    ai_governance_router,
    analytics_router,
    assignments_router,
    audit_router,
    auth_router,
    bulk_uploads_router,
    conversations_router,
    completion_router,
    documents_router,
    department_operations_router,
    external_access_router,
    health_router,
    organisation_router,
    operations_router,
    reviews_router,
    settings_router,
    teaching_contexts_router,
    teaching_outputs_router,
    users_router,
    workspace_router,
)

settings = get_settings()
configure_logging(level=settings.log_level, json_logs=settings.json_logs)
app = FastAPI(
    title=settings.app_name,
    version="2.5.0",
    description=(
        "Commercial Lecturer Support Agent with enterprise integration, account-security gap closure, "
        "governed real-data preparation, commercial release controls, and one unified AI workspace."
    ),
)
app.add_middleware(RequestContextMiddleware)
app.add_middleware(RequestMetricsMiddleware)
app.add_middleware(RateLimitMiddleware, settings=settings)
app.add_middleware(RequestSizeLimitMiddleware, settings=settings)
app.add_middleware(SecurityHeadersMiddleware, settings=settings)
app.add_middleware(
    CORSMiddleware,
    allow_origins=[item.strip() for item in settings.cors_allowed_origins.split(",") if item.strip()],
    allow_credentials=True,
    allow_methods=["GET", "POST", "PUT", "PATCH", "DELETE", "OPTIONS"],
    allow_headers=["Authorization", "Content-Type", "X-Request-ID", "X-Correlation-ID", "X-CSRF-Token"],
)
app.add_middleware(
    TrustedHostMiddleware,
    allowed_hosts=[item.strip() for item in settings.trusted_hosts.split(",") if item.strip()],
)


@app.exception_handler(ProviderError)
async def provider_error_handler(_: Request, exc: ProviderError) -> JSONResponse:
    """Return a safe provider failure without leaking credentials or raw payloads."""

    return JSONResponse(
        status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
        content={
            "detail": "No permitted AI provider could complete the request.",
            "error_code": exc.code,
        },
    )


app.include_router(health_router)
for router in (
    auth_router,
    analytics_router,
    ai_governance_router,
    audit_router,
    settings_router,
    users_router,
    organisation_router,
    operations_router,
    reviews_router,
    assignments_router,
    documents_router,
    department_operations_router,
    bulk_uploads_router,
    external_access_router,
    conversations_router,
    completion_router,
    teaching_contexts_router,
    teaching_outputs_router,
    workspace_router,
):
    app.include_router(router, prefix=settings.api_prefix)
