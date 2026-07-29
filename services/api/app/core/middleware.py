from __future__ import annotations

import hashlib
from uuid import UUID, uuid4

from fastapi import Request
from starlette.middleware.base import BaseHTTPMiddleware, RequestResponseEndpoint
from starlette.responses import JSONResponse, Response

from .request_context import RequestContext, reset_request_context, set_request_context
from .security import TokenService
from .settings import get_settings


PUBLIC_PATH_PREFIXES = (
    "/health",
    "/ready",
    "/metrics",
    "/api/v1/health",
    "/api/v1/ready",
    "/api/v1/auth/login",
    "/api/v1/auth/refresh",
    "/api/v1/auth/logout",
    "/api/v1/auth/invitations/accept",
    "/api/v1/auth/password-reset/",
    "/api/v1/auth/email-verification/",
    "/api/v1/auth/sso/",
    "/docs",
    "/redoc",
    "/openapi.json",
)


class RequestContextMiddleware(BaseHTTPMiddleware):
    """Build a fail-closed request context from a signed access token.

    Explicit development headers remain available only when the local setting
    is enabled. Production configuration must keep header authentication off.
    """

    async def dispatch(self, request: Request, call_next: RequestResponseEndpoint) -> Response:
        if any(request.url.path.startswith(prefix) for prefix in PUBLIC_PATH_PREFIXES):
            return await call_next(request)

        settings = get_settings()
        request_id = request.headers.get("x-request-id", str(uuid4()))
        correlation_id = request.headers.get("x-correlation-id", request_id)
        client_host = request.client.host if request.client else "unknown"
        source_ip_hash = hashlib.sha256(client_host.encode("utf-8")).hexdigest()

        authorization = request.headers.get("authorization", "")
        context: RequestContext | None = None
        if authorization.lower().startswith("bearer "):
            claims = TokenService(settings).decode_access_token(authorization.split(" ", 1)[1])
            context = RequestContext(
                tenant_id=claims.tenant_id,
                user_id=claims.subject,
                role_code=claims.role_code,
                correlation_id=correlation_id,
                membership_id=claims.membership_id,
                role_assignment_id=claims.role_assignment_id,
                session_id=claims.session_id,
                request_id=request_id,
                source_ip_hash=source_ip_hash,
            )
        elif settings.development_header_auth:
            context = self._development_context(
                request=request,
                correlation_id=correlation_id,
                request_id=request_id,
                source_ip_hash=source_ip_hash,
            )

        if context is None:
            return JSONResponse(
                status_code=401,
                content={"detail": "A valid bearer access token is required."},
                headers={"WWW-Authenticate": "Bearer"},
            )

        token = set_request_context(context)
        try:
            response = await call_next(request)
            response.headers["X-Request-ID"] = request_id
            response.headers["X-Correlation-ID"] = correlation_id
            return response
        finally:
            reset_request_context(token)

    @staticmethod
    def _development_context(
        *,
        request: Request,
        correlation_id: str,
        request_id: str,
        source_ip_hash: str,
    ) -> RequestContext | None:
        tenant_value = request.headers.get("x-tenant-id")
        user_value = request.headers.get("x-user-id")
        role_code = request.headers.get("x-role-code")
        if not all((tenant_value, user_value, role_code)):
            return None
        try:
            tenant_id = UUID(tenant_value)
            user_id = UUID(user_value)
            membership_id = (
                UUID(request.headers["x-membership-id"])
                if request.headers.get("x-membership-id")
                else None
            )
            role_assignment_id = (
                UUID(request.headers["x-role-assignment-id"])
                if request.headers.get("x-role-assignment-id")
                else None
            )
        except ValueError:
            return None
        return RequestContext(
            tenant_id=tenant_id,
            user_id=user_id,
            role_code=role_code,
            correlation_id=correlation_id,
            membership_id=membership_id,
            role_assignment_id=role_assignment_id,
            request_id=request_id,
            source_ip_hash=source_ip_hash,
        )
