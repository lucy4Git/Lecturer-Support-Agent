from __future__ import annotations

from dataclasses import dataclass
from uuid import UUID

from fastapi import HTTPException, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from services.database.models import Document, DocumentVersion, StorageObject

from ..core.request_context import RequestContext
from .authorization import AuthorizationService


@dataclass(frozen=True, slots=True)
class AccessibleVersion:
    document: Document
    version: DocumentVersion
    storage_object: StorageObject
    scope_type: str
    scope_id: UUID | None


class DocumentAccessService:
    def __init__(self, session: AsyncSession, context: RequestContext) -> None:
        self.session = session
        self.context = context
        self.authorization = AuthorizationService(session, context)

    async def require_version(self, version_id: UUID) -> AccessibleVersion:
        row = (
            await self.session.execute(
                select(Document, DocumentVersion, StorageObject)
                .join(DocumentVersion, DocumentVersion.document_id == Document.id)
                .join(StorageObject, StorageObject.id == DocumentVersion.storage_object_id)
                .where(
                    Document.tenant_id == self.context.tenant_id,
                    DocumentVersion.tenant_id == self.context.tenant_id,
                    StorageObject.tenant_id == self.context.tenant_id,
                    DocumentVersion.id == version_id,
                    Document.is_deleted.is_(False),
                )
            )
        ).first()
        if row is None:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Document version not found.")
        document, version, storage_object = row
        if document.visibility in {"private", "assigned_users"} and document.owner_user_id != self.context.user_id:
            raise HTTPException(status_code=403, detail="This document version is private to its owner.")
        scope_type, scope_id = self._scope(document)
        await self.authorization.require_permission(
            tenant_id=self.context.tenant_id,
            user_id=self.context.user_id,
            permission_code="content.read",
            scope_type=scope_type,
            scope_id=scope_id,
        )
        return AccessibleVersion(document, version, storage_object, scope_type, scope_id)

    @staticmethod
    def _scope(document: Document) -> tuple[str, UUID | None]:
        if document.module_id:
            return "module", document.module_id
        if document.programme_id:
            return "programme", document.programme_id
        if document.org_unit_id:
            return "organisational_unit", document.org_unit_id
        return "institution", None
