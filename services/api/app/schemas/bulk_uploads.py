from __future__ import annotations

from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, Field

from .common import ORMModel
from .documents import DocumentVersionResponse


class BulkUploadFileMetadata(BaseModel):
    client_item_key: str = Field(min_length=1, max_length=180)
    title: str = Field(min_length=1, max_length=500)
    document_type: str = Field(min_length=1, max_length=100)
    change_reason: str = Field(min_length=1, max_length=2000)
    existing_document_id: UUID | None = None
    metadata: dict = Field(default_factory=dict)


class BulkUploadRequestMetadata(BaseModel):
    scope_type: str | None = Field(default=None, min_length=1, max_length=60)
    scope_id: UUID | None = None
    change_reason: str = Field(min_length=1, max_length=2000)
    org_unit_id: UUID | None = None
    programme_id: UUID | None = None
    module_id: UUID | None = None
    files: list[BulkUploadFileMetadata]
    auto_process: bool = True
    expand_archives: bool = True
    visibility: str = "private"


class UploadBatchResponse(ORMModel):
    id: UUID
    tenant_id: UUID
    uploaded_by_user_id: UUID
    active_role_code: str
    scope_type: str
    scope_id: UUID | None
    status: str
    expected_item_count: int | None
    received_item_count: int
    completed_item_count: int
    failed_item_count: int
    completed_at: datetime | None


class BulkUploadItemResult(BaseModel):
    client_item_key: str
    original_filename: str
    status: str
    document_version_id: UUID | None = None
    validation_errors: list = Field(default_factory=list)


class BulkUploadResponse(BaseModel):
    batch: UploadBatchResponse
    versions: list[DocumentVersionResponse]
    items: list[BulkUploadItemResult] = Field(default_factory=list)
    processing: list[dict] = Field(default_factory=list)
