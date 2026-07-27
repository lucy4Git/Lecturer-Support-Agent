from __future__ import annotations

from contextvars import ContextVar, Token
from dataclasses import dataclass
from uuid import UUID


@dataclass(frozen=True, slots=True)
class RequestContext:
    tenant_id: UUID
    user_id: UUID
    role_code: str
    correlation_id: str
    membership_id: UUID | None = None
    role_assignment_id: UUID | None = None
    session_id: UUID | None = None
    request_id: str | None = None
    source_ip_hash: str | None = None


_context: ContextVar[RequestContext | None] = ContextVar("lsa_request_context", default=None)


def set_request_context(context: RequestContext) -> Token[RequestContext | None]:
    return _context.set(context)


def reset_request_context(token: Token[RequestContext | None]) -> None:
    _context.reset(token)


def get_request_context() -> RequestContext:
    context = _context.get()
    if context is None:
        raise RuntimeError("Request context is unavailable")
    return context


def get_request_context_optional() -> RequestContext | None:
    """Return the current context without raising for public or startup code."""
    return _context.get()
