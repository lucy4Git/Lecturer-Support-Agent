from __future__ import annotations

from datetime import datetime, timezone
from uuid import UUID

from fastapi import HTTPException, status
from sqlalchemy import func, or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from services.database.models import (
    AssignedReviewTask,
    Conversation,
    Document,
    DocumentVersion,
    GeneratedOutput,
    Message,
    Notification,
    OutputVersion,
    SavedOutput,
)

from ..core.request_context import RequestContext
from .authorization import AuthorizationService
from .document_access import DocumentAccessService


ROLE_ACTIONS: dict[str, list[str]] = {
    "institution_administrator": ["users", "roles", "institution_structure", "academic_calendar", "bulk_upload", "audit"],
    "head_of_department": ["module_assignments", "workload", "readiness", "moderation", "handovers", "bulk_upload"],
    "lecturer": ["teaching_plans", "assessments", "readiness", "handover", "bulk_upload"],
    "module_coordinator": ["module_alignment", "readiness", "moderation", "workload", "bulk_upload"],
    "programme_coordinator": ["programme_alignment", "readiness", "moderation", "workload", "bulk_upload"],
    "internal_moderator": ["review_tasks", "findings", "recommendations", "bulk_upload"],
    "external_moderator": ["review_tasks", "findings", "recommendations", "bulk_upload"],
    "external_reviewer": ["review_tasks", "findings", "recommendations", "bulk_upload"],
}


def navigation_for_role(role_code: str, unread_count: int = 0) -> dict:
    """Return a stable, server-owned navigation contract for the unified shell."""

    items = [
        {"key": "conversation", "label": "New conversation", "icon": "message", "enabled": True, "badge_count": 0},
        {"key": "search", "label": "Search", "icon": "search", "enabled": True, "badge_count": 0},
        {"key": "library", "label": "Library", "icon": "library", "enabled": True, "badge_count": 0},
        {"key": "files", "label": "Files", "icon": "file", "enabled": True, "badge_count": 0},
        {"key": "saved", "label": "Saved outputs", "icon": "bookmark", "enabled": True, "badge_count": 0},
        {"key": "notifications", "label": "Notifications", "icon": "bell", "enabled": True, "badge_count": unread_count},
    ]
    items.append({"key": "insights", "label": "Insights", "icon": "chart", "enabled": True, "badge_count": 0})
    if role_code in {"institution_administrator", "head_of_department", "module_coordinator", "programme_coordinator", "lecturer", "internal_moderator"}:
        items.append({"key": "reports", "label": "Reports", "icon": "report", "enabled": True, "badge_count": 0})
    if role_code == "institution_administrator":
        items.append({"key": "audit", "label": "Audit centre", "icon": "shield", "enabled": True, "badge_count": 0})
    if role_code == "institution_administrator":
        items.append({"key": "settings", "label": "Platform settings", "icon": "settings", "enabled": True, "badge_count": 0})
    return {
        "active_role": role_code,
        "items": items,
        "role_actions": ROLE_ACTIONS.get(role_code, ["bulk_upload"]),
    }


def normalise_search_query(query: str) -> str:
    cleaned = " ".join(query.strip().split())
    if len(cleaned) < 2:
        raise ValueError("Search query must contain at least two characters.")
    if len(cleaned) > 200:
        raise ValueError("Search query must not exceed 200 characters.")
    return cleaned


class WorkspaceService:
    def __init__(self, session: AsyncSession, context: RequestContext) -> None:
        self.session = session
        self.context = context
        self.authorization = AuthorizationService(session, context)

    async def unread_notification_count(self) -> int:
        return int(
            await self.session.scalar(
                select(func.count(Notification.id)).where(
                    Notification.tenant_id == self.context.tenant_id,
                    Notification.recipient_user_id == self.context.user_id,
                    Notification.read_at.is_(None),
                    Notification.archived_at.is_(None),
                    or_(Notification.expires_at.is_(None), Notification.expires_at > datetime.now(timezone.utc)),
                )
            )
            or 0
        )

    async def unified_search(self, query: str, kinds: set[str], limit: int) -> list[dict]:
        cleaned = normalise_search_query(query)
        pattern = f"%{cleaned}%"
        results: list[dict] = []

        if not kinds or "conversation" in kinds:
            rows = (
                await self.session.scalars(
                    select(Conversation)
                    .where(
                        Conversation.tenant_id == self.context.tenant_id,
                        Conversation.owner_user_id == self.context.user_id,
                        Conversation.is_archived.is_(False),
                        Conversation.title.ilike(pattern),
                    )
                    .order_by(Conversation.updated_at.desc())
                    .limit(limit)
                )
            ).all()
            results.extend(
                {
                    "kind": "conversation",
                    "id": item.id,
                    "title": item.title,
                    "snippet": "Conversation",
                    "updated_at": item.updated_at,
                    "action_path": f"conversation:{item.id}",
                    "metadata": {},
                }
                for item in rows
            )

        if not kinds or "output" in kinds:
            rows = (
                await self.session.execute(
                    select(GeneratedOutput, OutputVersion)
                    .join(Conversation, Conversation.id == GeneratedOutput.conversation_id)
                    .join(OutputVersion, OutputVersion.id == GeneratedOutput.current_version_id)
                    .where(
                        GeneratedOutput.tenant_id == self.context.tenant_id,
                        Conversation.owner_user_id == self.context.user_id,
                        or_(GeneratedOutput.title.ilike(pattern), OutputVersion.content_text.ilike(pattern)),
                    )
                    .order_by(GeneratedOutput.updated_at.desc())
                    .limit(limit)
                )
            ).all()
            results.extend(
                {
                    "kind": "output",
                    "id": output.id,
                    "title": output.title,
                    "snippet": version.content_text[:240],
                    "updated_at": output.updated_at,
                    "action_path": f"conversation:{output.conversation_id}",
                    "metadata": {"output_type": output.output_type, "version_number": version.version_number},
                }
                for output, version in rows
            )

        if not kinds or "document" in kinds:
            candidates = (
                await self.session.execute(
                    select(Document, DocumentVersion)
                    .join(DocumentVersion, DocumentVersion.id == Document.current_version_id)
                    .where(
                        Document.tenant_id == self.context.tenant_id,
                        Document.is_deleted.is_(False),
                        or_(Document.title.ilike(pattern), DocumentVersion.original_filename.ilike(pattern)),
                    )
                    .order_by(Document.updated_at.desc())
                    .limit(limit * 3)
                )
            ).all()
            access = DocumentAccessService(self.session, self.context)
            for document, version in candidates:
                try:
                    await access.require_version(version.id)
                except HTTPException:
                    continue
                results.append(
                    {
                        "kind": "document",
                        "id": document.id,
                        "title": document.title,
                        "snippet": version.original_filename,
                        "updated_at": document.updated_at,
                        "action_path": f"file:{version.id}",
                        "metadata": {
                            "document_version_id": str(version.id),
                            "document_type": document.document_type,
                            "version_number": version.version_number,
                        },
                    }
                )
                if len([item for item in results if item["kind"] == "document"]) >= limit:
                    break

        if not kinds or "review_task" in kinds:
            rows = (
                await self.session.scalars(
                    select(AssignedReviewTask)
                    .where(
                        AssignedReviewTask.tenant_id == self.context.tenant_id,
                        AssignedReviewTask.assigned_user_id == self.context.user_id,
                        or_(
                            AssignedReviewTask.task_type.ilike(pattern),
                            AssignedReviewTask.instructions.ilike(pattern),
                        ),
                    )
                    .order_by(AssignedReviewTask.updated_at.desc())
                    .limit(limit)
                )
            ).all()
            results.extend(
                {
                    "kind": "review_task",
                    "id": item.id,
                    "title": item.task_type.replace("_", " ").title(),
                    "snippet": item.instructions,
                    "updated_at": item.updated_at,
                    "action_path": "action:reviewTasks",
                    "metadata": {"status": item.status, "due_at": item.due_at.isoformat() if item.due_at else None},
                }
                for item in rows
            )

        results.sort(key=lambda item: item["updated_at"], reverse=True)
        return results[:limit]

    async def library_items(self, *, view: str, limit: int) -> list[dict]:
        statement = (
            select(Document, DocumentVersion)
            .join(DocumentVersion, DocumentVersion.id == Document.current_version_id)
            .where(
                Document.tenant_id == self.context.tenant_id,
                Document.is_deleted.is_(False),
            )
            .order_by(Document.updated_at.desc())
            .limit(limit * 4)
        )
        if view == "mine":
            statement = statement.where(Document.owner_user_id == self.context.user_id)
        elif view == "institutional":
            statement = statement.where(Document.visibility.in_(["institution", "department", "programme", "module", "public"]))

        candidates = (await self.session.execute(statement)).all()
        access = DocumentAccessService(self.session, self.context)
        items: list[dict] = []
        for document, version in candidates:
            try:
                await access.require_version(version.id)
            except HTTPException:
                continue
            access_label = "My file" if document.owner_user_id == self.context.user_id else "Shared with your scope"
            items.append(
                {
                    "document_id": document.id,
                    "document_version_id": version.id,
                    "title": document.title,
                    "document_type": document.document_type,
                    "original_filename": version.original_filename,
                    "version_number": version.version_number,
                    "version_status": version.status,
                    "visibility": document.visibility,
                    "owner_user_id": document.owner_user_id,
                    "updated_at": document.updated_at,
                    "module_id": document.module_id,
                    "programme_id": document.programme_id,
                    "org_unit_id": document.org_unit_id,
                    "indexed": version.indexed_at is not None,
                    "access_label": access_label,
                }
            )
            if len(items) >= limit:
                break
        return items

    async def save_output(self, payload: object) -> SavedOutput:
        from ..schemas.workspace import SavedOutputCreate

        data = payload if isinstance(payload, SavedOutputCreate) else SavedOutputCreate.model_validate(payload)
        output = await self.session.scalar(
            select(GeneratedOutput).where(
                GeneratedOutput.tenant_id == self.context.tenant_id,
                GeneratedOutput.id == data.generated_output_id,
            )
        )
        version = await self.session.scalar(
            select(OutputVersion).where(
                OutputVersion.tenant_id == self.context.tenant_id,
                OutputVersion.id == data.output_version_id,
                OutputVersion.generated_output_id == data.generated_output_id,
            )
        )
        if output is None or version is None:
            raise HTTPException(status_code=404, detail="Generated output version not found.")
        conversation_owner = await self.session.scalar(
            select(Conversation.owner_user_id).where(
                Conversation.tenant_id == self.context.tenant_id,
                Conversation.id == output.conversation_id,
            )
        )
        if conversation_owner != self.context.user_id:
            await self.authorization.require_permission(
                tenant_id=self.context.tenant_id,
                user_id=self.context.user_id,
                permission_code="outputs.review",
            )
        existing = await self.session.scalar(
            select(SavedOutput).where(
                SavedOutput.tenant_id == self.context.tenant_id,
                SavedOutput.user_id == self.context.user_id,
                SavedOutput.output_version_id == data.output_version_id,
            )
        )
        if existing:
            existing.label = data.label or existing.label
            existing.note = data.note
            existing.folder = data.folder
            existing.tags = data.tags
            existing.is_pinned = data.is_pinned
            await self.session.flush()
            return existing
        saved = SavedOutput(
            tenant_id=self.context.tenant_id,
            user_id=self.context.user_id,
            generated_output_id=data.generated_output_id,
            output_version_id=data.output_version_id,
            label=data.label,
            note=data.note,
            folder=data.folder,
            tags=data.tags,
            is_pinned=data.is_pinned,
        )
        self.session.add(saved)
        await self.session.flush()
        return saved

    async def saved_outputs(self, limit: int) -> list[dict]:
        rows = (
            await self.session.execute(
                select(SavedOutput, GeneratedOutput, OutputVersion)
                .join(GeneratedOutput, GeneratedOutput.id == SavedOutput.generated_output_id)
                .join(OutputVersion, OutputVersion.id == SavedOutput.output_version_id)
                .where(
                    SavedOutput.tenant_id == self.context.tenant_id,
                    SavedOutput.user_id == self.context.user_id,
                )
                .order_by(SavedOutput.is_pinned.desc(), SavedOutput.updated_at.desc())
                .limit(limit)
            )
        ).all()
        return [
            {
                "id": saved.id,
                "created_at": saved.created_at,
                "updated_at": saved.updated_at,
                "user_id": saved.user_id,
                "generated_output_id": saved.generated_output_id,
                "output_version_id": saved.output_version_id,
                "label": saved.label,
                "note": saved.note,
                "folder": saved.folder,
                "tags": saved.tags,
                "is_pinned": saved.is_pinned,
                "output_title": output.title,
                "output_type": output.output_type,
                "version_number": version.version_number,
                "content_preview": version.content_text[:300],
            }
            for saved, output, version in rows
        ]

    async def delete_saved_output(self, saved_id: UUID) -> None:
        saved = await self.session.scalar(
            select(SavedOutput).where(
                SavedOutput.tenant_id == self.context.tenant_id,
                SavedOutput.id == saved_id,
                SavedOutput.user_id == self.context.user_id,
            )
        )
        if saved is None:
            raise HTTPException(status_code=404, detail="Saved output not found.")
        await self.session.delete(saved)
        await self.session.flush()

    async def notifications(self, *, unread_only: bool, limit: int) -> list[Notification]:
        statement = select(Notification).where(
            Notification.tenant_id == self.context.tenant_id,
            Notification.recipient_user_id == self.context.user_id,
            Notification.archived_at.is_(None),
            or_(Notification.expires_at.is_(None), Notification.expires_at > datetime.now(timezone.utc)),
        )
        if unread_only:
            statement = statement.where(Notification.read_at.is_(None))
        return list((await self.session.scalars(statement.order_by(Notification.created_at.desc()).limit(limit))).all())

    async def mark_notification(self, notification_id: UUID, read: bool) -> Notification:
        notification = await self.session.scalar(
            select(Notification).where(
                Notification.tenant_id == self.context.tenant_id,
                Notification.id == notification_id,
                Notification.recipient_user_id == self.context.user_id,
            )
        )
        if notification is None:
            raise HTTPException(status_code=404, detail="Notification not found.")
        notification.read_at = datetime.now(timezone.utc) if read else None
        await self.session.flush()
        return notification

    async def mark_all_notifications_read(self) -> int:
        items = await self.notifications(unread_only=True, limit=500)
        now = datetime.now(timezone.utc)
        for item in items:
            item.read_at = now
        await self.session.flush()
        return len(items)

    async def summary(self) -> dict:
        recent_conversations = int(
            await self.session.scalar(
                select(func.count(Conversation.id)).where(
                    Conversation.tenant_id == self.context.tenant_id,
                    Conversation.owner_user_id == self.context.user_id,
                    Conversation.is_archived.is_(False),
                )
            )
            or 0
        )
        saved_outputs = int(
            await self.session.scalar(
                select(func.count(SavedOutput.id)).where(
                    SavedOutput.tenant_id == self.context.tenant_id,
                    SavedOutput.user_id == self.context.user_id,
                )
            )
            or 0
        )
        assigned_review_tasks = int(
            await self.session.scalar(
                select(func.count(AssignedReviewTask.id)).where(
                    AssignedReviewTask.tenant_id == self.context.tenant_id,
                    AssignedReviewTask.assigned_user_id == self.context.user_id,
                    AssignedReviewTask.status.in_(["assigned", "accepted", "in_progress", "returned"]),
                )
            )
            or 0
        )
        personal_files = int(
            await self.session.scalar(
                select(func.count(Document.id)).where(
                    Document.tenant_id == self.context.tenant_id,
                    Document.owner_user_id == self.context.user_id,
                    Document.is_deleted.is_(False),
                )
            )
            or 0
        )
        library_items = len(await self.library_items(view="all", limit=250))
        return {
            "recent_conversations": recent_conversations,
            "library_items": library_items,
            "personal_files": personal_files,
            "saved_outputs": saved_outputs,
            "unread_notifications": await self.unread_notification_count(),
            "assigned_review_tasks": assigned_review_tasks,
        }
