from __future__ import annotations

import hashlib
import logging
import time
from dataclasses import dataclass

from fastapi import Request
from starlette.middleware.base import BaseHTTPMiddleware, RequestResponseEndpoint
from starlette.responses import JSONResponse, Response
from starlette.types import ASGIApp, Message, Receive, Scope, Send

from ..observability.metrics import METRICS
from .settings import Settings, get_settings

logger = logging.getLogger("lsa.http")


class SecurityHeadersMiddleware(BaseHTTPMiddleware):
    def __init__(self, app, settings: Settings | None = None) -> None:
        super().__init__(app)
        self.settings = settings or get_settings()

    async def dispatch(self, request: Request, call_next: RequestResponseEndpoint) -> Response:
        response = await call_next(request)
        response.headers.setdefault("X-Content-Type-Options", "nosniff")
        response.headers.setdefault("X-Frame-Options", "DENY")
        response.headers.setdefault("Referrer-Policy", "strict-origin-when-cross-origin")
        response.headers.setdefault("Permissions-Policy", "camera=(), microphone=(), geolocation=(), payment=()")
        response.headers.setdefault("Cross-Origin-Opener-Policy", "same-origin")
        response.headers.setdefault("Cross-Origin-Resource-Policy", "same-site")
        response.headers.setdefault("Content-Security-Policy", self.settings.content_security_policy)
        if self.settings.environment.lower() == "production":
            response.headers.setdefault("Strict-Transport-Security", "max-age=31536000; includeSubDomains; preload")
        if request.url.path.startswith(("/api/v1/auth", "/api/v1/audit-centre", "/api/v1/platform-settings")):
            response.headers.setdefault("Cache-Control", "no-store")
        return response


class _RequestBodyTooLarge(Exception):
    pass


class RequestSizeLimitMiddleware:
    """Enforce request limits for both declared and streamed request bodies."""

    def __init__(self, app: ASGIApp, settings: Settings | None = None) -> None:
        self.app = app
        self.settings = settings or get_settings()

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        if scope["type"] != "http":
            await self.app(scope, receive, send)
            return

        headers = {key.lower(): value for key, value in scope.get("headers", [])}
        content_length = headers.get(b"content-length")
        if content_length is not None:
            try:
                declared_size = int(content_length.decode("ascii"))
            except (UnicodeDecodeError, ValueError):
                response = JSONResponse(status_code=400, content={"detail": "Invalid Content-Length header."})
                await response(scope, receive, send)
                return
            if declared_size > self.settings.maximum_request_bytes:
                response = JSONResponse(status_code=413, content={"detail": "Request exceeds the configured size limit."})
                await response(scope, receive, send)
                return

        received_bytes = 0
        response_started = False

        async def limited_receive() -> Message:
            nonlocal received_bytes
            message = await receive()
            if message["type"] == "http.request":
                received_bytes += len(message.get("body", b""))
                if received_bytes > self.settings.maximum_request_bytes:
                    raise _RequestBodyTooLarge
            return message

        async def tracked_send(message: Message) -> None:
            nonlocal response_started
            if message["type"] == "http.response.start":
                response_started = True
            await send(message)

        try:
            await self.app(scope, limited_receive, tracked_send)
        except _RequestBodyTooLarge:
            if response_started:
                logger.error("Request body exceeded limit after response start")
                return
            response = JSONResponse(status_code=413, content={"detail": "Request exceeds the configured size limit."})
            await response(scope, receive, send)


@dataclass(frozen=True, slots=True)
class RateLimitResult:
    allowed: bool
    remaining: int
    retry_after_seconds: int


class RedisRateLimiter:
    def __init__(self, settings: Settings | None = None, gateway: object | None = None) -> None:
        self.settings = settings or get_settings()
        self.gateway = gateway

    async def check(self, key: str, *, limit: int, window_seconds: int) -> RateLimitResult:
        if self.gateway is None:
            from ..integrations.redis_gateway import RedisGateway
            self.gateway = RedisGateway(self.settings)
        redis_key = f"lsa:rate-limit:{key}"
        script = """
        local value = redis.call('INCR', KEYS[1])
        if value == 1 then redis.call('EXPIRE', KEYS[1], ARGV[1]) end
        local ttl = redis.call('TTL', KEYS[1])
        return {value, ttl}
        """
        value, ttl = await self.gateway.client.eval(script, 1, redis_key, window_seconds)
        return RateLimitResult(
            allowed=int(value) <= limit,
            remaining=max(0, limit - int(value)),
            retry_after_seconds=max(1, int(ttl)),
        )


class RateLimitMiddleware(BaseHTTPMiddleware):
    def __init__(self, app, settings: Settings | None = None) -> None:
        super().__init__(app)
        self.settings = settings or get_settings()
        self.limiter = RedisRateLimiter(self.settings)

    async def dispatch(self, request: Request, call_next: RequestResponseEndpoint) -> Response:
        if not self.settings.rate_limit_enabled or request.url.path in {"/health", "/ready", "/metrics"}:
            return await call_next(request)
        client = request.client.host if request.client else "unknown"
        credential = request.headers.get("authorization", "anonymous")
        identity = hashlib.sha256(f"{client}:{credential[:64]}".encode()).hexdigest()[:32]
        sensitive = request.url.path.startswith(("/api/v1/auth/login", "/api/v1/auth/refresh"))
        limit = self.settings.auth_rate_limit_per_minute if sensitive else self.settings.api_rate_limit_per_minute
        key = f"{identity}:{request.url.path.split('?', 1)[0]}"
        try:
            result = await self.limiter.check(key, limit=limit, window_seconds=60)
        except Exception:
            logger.exception("Rate limiter unavailable")
            if self.settings.environment.lower() == "production" and self.settings.rate_limit_fail_closed:
                return JSONResponse(status_code=503, content={"detail": "Request protection service unavailable."})
            return await call_next(request)
        if not result.allowed:
            METRICS.increment("lsa_rate_limit_rejections_total", labels={"path": request.url.path})
            return JSONResponse(
                status_code=429,
                content={"detail": "Too many requests."},
                headers={"Retry-After": str(result.retry_after_seconds), "X-RateLimit-Remaining": "0"},
            )
        response = await call_next(request)
        response.headers["X-RateLimit-Remaining"] = str(result.remaining)
        return response


class RequestMetricsMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next: RequestResponseEndpoint) -> Response:
        started = time.perf_counter()
        status_code = 500
        try:
            response = await call_next(request)
            status_code = response.status_code
            return response
        finally:
            duration_ms = (time.perf_counter() - started) * 1000
            parts = request.url.path.split("/")
            route_group = parts[3] if request.url.path.startswith("/api/") and len(parts) > 3 else request.url.path
            METRICS.increment("lsa_http_requests_total", labels={"method": request.method, "route_group": route_group, "status": str(status_code)})
            METRICS.increment("lsa_http_request_duration_ms_total", duration_ms, labels={"method": request.method, "route_group": route_group})
            logger.info(
                "request.completed",
                extra={"event": "request.completed", "duration_ms": round(duration_ms, 2), "status_code": status_code, "path": request.url.path, "method": request.method},
            )
