from __future__ import annotations

from datetime import datetime
from typing import Literal
from uuid import UUID

from pydantic import BaseModel, Field

from .common import AuditFields


WorkspaceView = Literal["conversation", "search", "library", "files", "saved", "notifications", "insights", "reports", "audit", "settings"]


class NavigationItem(BaseModel):
    key: WorkspaceView
    label: str
    icon: str
    enabled: bool = True
    badge_count: int = 0


class WorkspaceNavigationResponse(BaseModel):
    active_role: str
    items: list[NavigationItem]
    role_actions: list[str]


class SearchResult(BaseModel):
    kind: str
    id: UUID
    title: str
    snippet: str | None = None
    updated_at: datetime
    action_path: str | None = None
    metadata: dict = Field(default_factory=dict)


class UnifiedSearchResponse(BaseModel):
    query: str
    total: int
    results: list[SearchResult]


class LibraryItem(BaseModel):
    document_id: UUID
    document_version_id: UUID
    title: str
    document_type: str
    original_filename: str
    version_number: int
    version_status: str
    visibility: str
    owner_user_id: UUID
    updated_at: datetime
    module_id: UUID | None = None
    programme_id: UUID | None = None
    org_unit_id: UUID | None = None
    indexed: bool
    access_label: str


class LibraryResponse(BaseModel):
    total: int
    items: list[LibraryItem]


class SavedOutputCreate(BaseModel):
    generated_output_id: UUID
    output_version_id: UUID
    label: str | None = Field(default=None, max_length=300)
    note: str | None = Field(default=None, max_length=4000)
    folder: str | None = Field(default=None, max_length=160)
    tags: list[str] = Field(default_factory=list, max_length=20)
    is_pinned: bool = False


class SavedOutputUpdate(BaseModel):
    label: str | None = Field(default=None, max_length=300)
    note: str | None = Field(default=None, max_length=4000)
    folder: str | None = Field(default=None, max_length=160)
    tags: list[str] | None = Field(default=None, max_length=20)
    is_pinned: bool | None = None


class SavedOutputResponse(AuditFields):
    user_id: UUID
    generated_output_id: UUID
    output_version_id: UUID
    label: str | None
    note: str | None
    folder: str | None
    tags: list
    is_pinned: bool
    output_title: str | None = None
    output_type: str | None = None
    version_number: int | None = None
    content_preview: str | None = None


class NotificationResponse(AuditFields):
    recipient_user_id: UUID
    notification_type: str
    title: str
    body: str
    severity: str
    action_path: str | None
    resource_type: str | None
    resource_id: UUID | None
    read_at: datetime | None
    archived_at: datetime | None
    expires_at: datetime | None
    notification_metadata: dict


class NotificationListResponse(BaseModel):
    unread_count: int
    total: int
    items: list[NotificationResponse]


class NotificationMarkRequest(BaseModel):
    read: bool = True


class WorkspaceSummaryResponse(BaseModel):
    recent_conversations: int
    library_items: int
    personal_files: int
    saved_outputs: int
    unread_notifications: int
    assigned_review_tasks: int
