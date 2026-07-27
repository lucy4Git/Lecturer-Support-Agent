from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from uuid import UUID, uuid4

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from services.database.models import (
    Document, DocumentVersion, DocumentVersionTransition, StorageObject
)

from ..core.request_context import RequestContext
from ..integrations.object_storage import ObjectStorage, build_object_key
from .audit import AuditService
from .authorization import AuthorizationService


DOCUMENT_VERSION_TRANSITIONS: dict[str, set[str]] = {
    "working": {"under_review", "archived"},
    "under_review": {"working", "approved", "rejected", "archived"},
    "approved": {"published", "superseded", "archived"},
    "published": {"superseded", "archived"},
    "rejected": {"working", "archived"},
    "superseded": {"archived"},
    "archived": set(),
}


def is_document_version_transition_allowed(from_status: str, to_status: str) -> bool:
    return to_status in DOCUMENT_VERSION_TRANSITIONS.get(from_status, set())


@dataclass(frozen=True, slots=True)
class VersioningResult:
    document: Document
    version: DocumentVersion
    exact_duplicate: bool


class DocumentVersioningService:
    def __init__(
        self,
        *,
        session: AsyncSession,
        storage: ObjectStorage,
        context: RequestContext,
    ) -> None:
        self.session = session
        self.storage = storage
        self.context = context
        self.audit = AuditService(session, context)

    async def create_version(
        self,
        *,
        title: str,
        document_type: str,
        filename: str,
        content: bytes,
        media_type: str | None,
        change_reason: str,
        visibility: str = "private",
        document_id: UUID | None = None,
        org_unit_id: UUID | None = None,
        programme_id: UUID | None = None,
        module_id: UUID | None = None,
        upload_batch_id: UUID | None = None,
        provenance: dict | None = None,
        metadata: dict | None = None,
    ) -> VersioningResult:
        if not content:
            raise ValueError("An empty file cannot create a document version.")

        document: Document | None = None
        if document_id is not None:
            statement = (
                select(Document)
                .where(Document.id == document_id, Document.tenant_id == self.context.tenant_id)
                .with_for_update()
            )
            document = await self.session.scalar(statement)
            if document is None:
                raise ValueError("Document not found in the current tenant.")
            if document.visibility in {"private", "assigned_users"} and document.owner_user_id != self.context.user_id:
                raise PermissionError("This document is private to its owner and cannot be versioned by this user.")

        target_org_unit_id = org_unit_id if org_unit_id is not None else (document.org_unit_id if document else None)
        target_programme_id = programme_id if programme_id is not None else (document.programme_id if document else None)
        target_module_id = module_id if module_id is not None else (document.module_id if document else None)
        scope_type = (
            "module" if target_module_id else
            "programme" if target_programme_id else
            "organisational_unit" if target_org_unit_id else
            "institution"
        )
        scope_id = target_module_id or target_programme_id or target_org_unit_id
        await AuthorizationService(self.session, self.context).require_permission(
            tenant_id=self.context.tenant_id,
            user_id=self.context.user_id,
            permission_code="content.upload",
            scope_type=scope_type,
            scope_id=scope_id,
        )

        digest = __import__("hashlib").sha256(content).hexdigest()
        if document is not None:
            duplicate = await self.session.scalar(
                select(DocumentVersion).where(
                    DocumentVersion.tenant_id == self.context.tenant_id,
                    DocumentVersion.document_id == document.id,
                    DocumentVersion.sha256 == digest,
                )
            )
            if duplicate is not None:
                await self.audit.record(
                    action="document.exact_duplicate_detected",
                    resource_type="document_version",
                    resource_id=duplicate.id,
                    metadata={"filename": filename, "sha256": digest},
                )
                return VersioningResult(document=document, version=duplicate, exact_duplicate=True)

        if document is None:
            document = Document(
                id=document_id or uuid4(),
                tenant_id=self.context.tenant_id,
                title=title,
                document_type=document_type,
                owner_user_id=self.context.user_id,
                org_unit_id=org_unit_id,
                programme_id=programme_id,
                module_id=module_id,
                visibility=visibility,
                metadata_payload=metadata or {},
            )
            self.session.add(document)
            await self.session.flush()
            version_number = 1
        else:
            maximum = await self.session.scalar(
                select(func.max(DocumentVersion.version_number)).where(
                    DocumentVersion.tenant_id == self.context.tenant_id,
                    DocumentVersion.document_id == document.id,
                )
            )
            version_number = int(maximum or 0) + 1

        previous_version_id = document.current_version_id
        object_key = build_object_key(
            tenant_id=self.context.tenant_id,
            document_id=document.id,
            version_number=version_number,
            filename=Path(filename).name,
        )
        stored = await self.storage.put_bytes(
            tenant_id=self.context.tenant_id,
            object_key=object_key,
            content=content,
            media_type=media_type,
            metadata={"document-id": str(document.id), "version-number": str(version_number)},
        )
        storage_object = StorageObject(
            id=uuid4(),
            tenant_id=self.context.tenant_id,
            provider="s3",
            bucket_name=stored.bucket_name,
            object_key=stored.object_key,
            storage_version_id=stored.storage_version_id,
            etag=stored.etag,
            sha256=stored.sha256,
            size_bytes=stored.size_bytes,
            media_type=stored.media_type,
        )
        self.session.add(storage_object)
        version = DocumentVersion(
            id=uuid4(),
            tenant_id=self.context.tenant_id,
            document_id=document.id,
            version_number=version_number,
            previous_version_id=previous_version_id,
            storage_object_id=storage_object.id,
            upload_batch_id=upload_batch_id,
            uploaded_by_user_id=self.context.user_id,
            uploader_role_code=self.context.role_code,
            original_filename=Path(filename).name,
            sha256=stored.sha256,
            status="working",
            change_reason=change_reason,
            provenance=provenance or {"source": "user_upload"},
        )
        self.session.add(version)
        document.current_version_id = version.id
        document.title = title
        document.document_type = document_type
        document.org_unit_id = org_unit_id if org_unit_id is not None else document.org_unit_id
        document.programme_id = programme_id if programme_id is not None else document.programme_id
        document.module_id = module_id if module_id is not None else document.module_id
        await self.session.flush()
        await self.audit.record(
            action="document.version_created",
            resource_type="document_version",
            resource_id=version.id,
            after_state={
                "document_id": str(document.id),
                "version_number": version_number,
                "sha256": stored.sha256,
                "storage_version_id": stored.storage_version_id,
            },
            metadata={"filename": filename, "change_reason": change_reason},
        )
        return VersioningResult(document=document, version=version, exact_duplicate=False)

    async def transition_status(
        self,
        *,
        version_id: UUID,
        to_status: str,
        reason: str,
    ) -> DocumentVersionTransition:
        """Apply an explicit, append-only lifecycle transition.

        Status history is never overwritten. Approval and publication require
        the stronger approval permission; review-stage transitions require the
        review permission.
        """
        row = (
            await self.session.execute(
                select(Document, DocumentVersion)
                .join(DocumentVersion, DocumentVersion.document_id == Document.id)
                .where(
                    Document.tenant_id == self.context.tenant_id,
                    DocumentVersion.tenant_id == self.context.tenant_id,
                    DocumentVersion.id == version_id,
                    Document.is_deleted.is_(False),
                )
                .with_for_update()
            )
        ).first()
        if row is None:
            raise ValueError("Document version not found in the current tenant.")
        document, version = row
        if document.visibility in {"private", "assigned_users"} and document.owner_user_id != self.context.user_id:
            raise PermissionError("This document version is private to its owner.")

        current = version.status
        if to_status == current:
            raise ValueError("The document version already has the requested status.")
        if not is_document_version_transition_allowed(current, to_status):
            raise ValueError(f"Transition from {current} to {to_status} is not allowed.")

        scope_type = (
            "module" if document.module_id else
            "programme" if document.programme_id else
            "organisational_unit" if document.org_unit_id else
            "institution"
        )
        scope_id = document.module_id or document.programme_id or document.org_unit_id
        permission_code = (
            "content.version.approve"
            if to_status in {"approved", "published", "superseded"}
            else "content.version.review"
        )
        await AuthorizationService(self.session, self.context).require_permission(
            tenant_id=self.context.tenant_id,
            user_id=self.context.user_id,
            permission_code=permission_code,
            scope_type=scope_type,
            scope_id=scope_id,
        )
        transition = DocumentVersionTransition(
            id=uuid4(),
            tenant_id=self.context.tenant_id,
            document_version_id=version.id,
            from_status=current,
            to_status=to_status,
            changed_by_user_id=self.context.user_id,
            changed_by_role_code=self.context.role_code,
            reason=reason,
            transition_metadata={
                "permission_code": permission_code,
                "scope_type": scope_type,
                "scope_id": str(scope_id) if scope_id else None,
            },
        )
        version.status = to_status
        self.session.add(transition)
        await self.audit.record(
            action="document.version_status_changed",
            resource_type="document_version",
            resource_id=version.id,
            before_state={"status": current},
            after_state={"status": to_status},
            metadata={"reason": reason, "transition_id": str(transition.id)},
        )
        await self.session.flush()
        return transition
