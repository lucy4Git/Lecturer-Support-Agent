from __future__ import annotations

from datetime import datetime, timezone
from uuid import UUID, uuid4

from fastapi import HTTPException
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from services.database.models import IntegrationConnection, IntegrationSyncRun, SSOConnection

from ..core.request_context import RequestContext
from ..core.settings import Settings, get_settings
from ..integrations.academic_systems import build_academic_adapter
from ..schemas.completion import IntegrationConnectionCreate, IntegrationSyncRequest, SSOConnectionCreate
from .audit import AuditService
from .job_queue import JobQueueService


class EnterpriseIntegrationService:
    def __init__(self, session: AsyncSession, context: RequestContext, settings: Settings | None = None) -> None:
        self.session = session
        self.context = context
        self.settings = settings or get_settings()
        self.audit = AuditService(session, context)

    async def list_connections(self) -> list[IntegrationConnection]:
        return list(await self.session.scalars(
            select(IntegrationConnection).where(IntegrationConnection.tenant_id == self.context.tenant_id).order_by(IntegrationConnection.display_name)
        ))

    async def create_connection(self, payload: IntegrationConnectionCreate) -> IntegrationConnection:
        existing = await self.session.scalar(select(IntegrationConnection).where(
            IntegrationConnection.tenant_id == self.context.tenant_id,
            IntegrationConnection.code == payload.code,
        ))
        if existing is not None:
            raise HTTPException(status_code=409, detail="Integration connection code already exists.")
        item = IntegrationConnection(
            id=uuid4(), tenant_id=self.context.tenant_id,
            code=payload.code, display_name=payload.display_name,
            integration_type=payload.integration_type, base_url=payload.base_url,
            authentication_type=payload.authentication_type,
            secret_reference=payload.secret_reference, status="configured",
            capabilities=payload.capabilities, configuration=payload.configuration,
        )
        self.session.add(item); await self.session.flush()
        await self.audit.record(
            action="integration.connection_created", resource_type="integration_connection", resource_id=item.id,
            after_state={"code": item.code, "integration_type": item.integration_type, "secret_reference": bool(item.secret_reference)},
        )
        return item

    async def test_connection(self, connection_id: UUID) -> IntegrationConnection:
        item = await self._get_connection(connection_id, for_update=True)
        adapter = build_academic_adapter(
            integration_type=item.integration_type, base_url=item.base_url,
            secret_reference=item.secret_reference, configuration=item.configuration,
            settings=self.settings,
        )
        try:
            result = await adapter.test_connection()
            item.last_tested_at = datetime.now(timezone.utc)
            item.last_test_status = "passed" if result.ok else "failed"
            item.capabilities = sorted(set(item.capabilities) | set(result.capabilities))
            item.status = "active" if result.ok else "error"
            item.configuration = {**item.configuration, "last_test_detail": result.detail}
        except (ValueError, RuntimeError, OSError) as exc:
            item.last_tested_at = datetime.now(timezone.utc); item.last_test_status = "failed"; item.status = "error"
            item.configuration = {**item.configuration, "last_test_detail": str(exc)[:1000]}
        await self.audit.record(
            action="integration.connection_tested", resource_type="integration_connection", resource_id=item.id,
            after_state={"status": item.last_test_status},
        )
        return item

    async def request_sync(self, connection_id: UUID, payload: IntegrationSyncRequest) -> IntegrationSyncRun:
        connection = await self._get_connection(connection_id)
        run = IntegrationSyncRun(
            id=uuid4(), tenant_id=self.context.tenant_id, connection_id=connection.id,
            sync_type=payload.sync_type, direction=payload.direction, status="queued",
            requested_by_user_id=self.context.user_id, cursor=payload.cursor,
        )
        self.session.add(run); await self.session.flush()
        await JobQueueService(self.session).enqueue(
            tenant_id=self.context.tenant_id,
            job_type="integrations.sync",
            payload={"sync_run_id": str(run.id)},
            requested_by_user_id=self.context.user_id,
            correlation_id=self.context.correlation_id,
            idempotency_key=f"integration-sync:{run.id}",
        )
        await self.audit.record(
            action="integration.sync_requested", resource_type="integration_sync_run", resource_id=run.id,
            after_state={"connection_id": str(connection.id), "sync_type": payload.sync_type, "direction": payload.direction},
        )
        return run

    async def list_sso_connections(self) -> list[SSOConnection]:
        return list(await self.session.scalars(
            select(SSOConnection).where(SSOConnection.tenant_id == self.context.tenant_id).order_by(SSOConnection.display_name)
        ))

    async def create_sso_connection(self, payload: SSOConnectionCreate) -> SSOConnection:
        if payload.protocol == "saml" and not payload.client_secret_reference:
            # SAML metadata can be public, but a secret reference or certificate reference is required for production trust.
            pass
        existing = await self.session.scalar(select(SSOConnection).where(
            SSOConnection.tenant_id == self.context.tenant_id,
            SSOConnection.code == payload.code,
        ))
        if existing is not None:
            raise HTTPException(status_code=409, detail="SSO connection code already exists.")
        item = SSOConnection(
            id=uuid4(), tenant_id=self.context.tenant_id,
            code=payload.code, display_name=payload.display_name, protocol=payload.protocol,
            issuer_url=payload.issuer_url, client_id=payload.client_id,
            client_secret_reference=payload.client_secret_reference, scopes=payload.scopes,
            claim_mapping=payload.claim_mapping, default_role_code=payload.default_role_code,
            is_enabled=payload.is_enabled,
            metadata_payload={
                "redirect_uris": payload.redirect_uris,
                "allow_account_linking_by_verified_email": payload.allow_account_linking_by_verified_email,
            },
        )
        self.session.add(item); await self.session.flush()
        await self.audit.record(
            action="identity.sso_connection_created", resource_type="sso_connection", resource_id=item.id,
            after_state={"protocol": item.protocol, "issuer_url": item.issuer_url, "client_secret_reference": bool(item.client_secret_reference)},
        )
        return item

    async def _get_connection(self, connection_id: UUID, *, for_update: bool = False) -> IntegrationConnection:
        query = select(IntegrationConnection).where(
            IntegrationConnection.tenant_id == self.context.tenant_id,
            IntegrationConnection.id == connection_id,
        )
        if for_update:
            query = query.with_for_update()
        item = await self.session.scalar(query)
        if item is None:
            raise HTTPException(status_code=404, detail="Integration connection was not found.")
        return item
