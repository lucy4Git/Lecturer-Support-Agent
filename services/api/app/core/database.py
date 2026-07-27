from __future__ import annotations

from collections.abc import AsyncIterator
from datetime import datetime, timezone
from functools import lru_cache

from fastapi import HTTPException, status
from sqlalchemy import select, text
from sqlalchemy.ext.asyncio import AsyncEngine, AsyncSession, async_sessionmaker, create_async_engine

from .request_context import get_request_context
from .settings import get_settings


@lru_cache(maxsize=1)
def get_application_engine() -> AsyncEngine:
    settings = get_settings()
    return create_async_engine(
        settings.database_url.get_secret_value(),
        pool_pre_ping=True,
        pool_size=10,
        max_overflow=20,
    )


@lru_cache(maxsize=1)
def get_worker_engine() -> AsyncEngine:
    settings = get_settings()
    return create_async_engine(
        settings.worker_database_url.get_secret_value(),
        pool_pre_ping=True,
        pool_size=5,
        max_overflow=10,
    )


@lru_cache(maxsize=1)
def get_authentication_engine() -> AsyncEngine:
    settings = get_settings()
    return create_async_engine(
        settings.auth_database_url.get_secret_value(),
        pool_pre_ping=True,
        pool_size=5,
        max_overflow=10,
    )


def get_session_factory() -> async_sessionmaker[AsyncSession]:
    return async_sessionmaker(
        get_application_engine(),
        expire_on_commit=False,
        class_=AsyncSession,
    )


def get_auth_session_factory() -> async_sessionmaker[AsyncSession]:
    return async_sessionmaker(
        get_authentication_engine(),
        expire_on_commit=False,
        class_=AsyncSession,
    )


async def apply_database_request_context(session: AsyncSession) -> None:
    """Apply transaction-local RLS context."""

    context = get_request_context()
    values = {
        "app.tenant_id": str(context.tenant_id),
        "app.user_id": str(context.user_id),
        "app.role_code": context.role_code,
        "app.correlation_id": context.correlation_id,
        "app.membership_id": str(context.membership_id or ""),
        "app.role_assignment_id": str(context.role_assignment_id or ""),
        "app.session_id": str(context.session_id or ""),
    }
    for key, value in values.items():
        await session.execute(
            text("SELECT set_config(:key, :value, true)"),
            {"key": key, "value": value},
        )


async def set_auth_tenant_context(session: AsyncSession, tenant_id: str) -> None:
    await session.execute(
        text("SELECT set_config('app.tenant_id', :value, true)"),
        {"value": tenant_id},
    )


async def validate_active_access_session(session: AsyncSession) -> None:
    """Reject access tokens whose backing session is revoked or expired.

    Access JWTs are still short lived, but this database check makes logout,
    role-session revocation, and refresh-token rotation effective immediately.
    Development header authentication has no session identifier and is allowed
    only when explicitly enabled outside production.
    """

    context = get_request_context()
    if context.session_id is None:
        return
    from services.database.models import AuthenticationSession

    active_session = await session.scalar(
        select(AuthenticationSession.id).where(
            AuthenticationSession.tenant_id == context.tenant_id,
            AuthenticationSession.id == context.session_id,
            AuthenticationSession.user_id == context.user_id,
            AuthenticationSession.membership_id == context.membership_id,
            AuthenticationSession.role_assignment_id == context.role_assignment_id,
            AuthenticationSession.status == "active",
            AuthenticationSession.expires_at > datetime.now(timezone.utc),
        )
    )
    if active_session is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="The authenticated session is no longer active.",
            headers={"WWW-Authenticate": "Bearer"},
        )


async def get_session() -> AsyncIterator[AsyncSession]:
    factory = get_session_factory()
    async with factory() as session:
        async with session.begin():
            await apply_database_request_context(session)
            await validate_active_access_session(session)
            yield session


async def get_auth_session() -> AsyncIterator[AsyncSession]:
    """Restricted session for public login, refresh, and invitation acceptance."""

    factory = get_auth_session_factory()
    async with factory() as session:
        async with session.begin():
            yield session
