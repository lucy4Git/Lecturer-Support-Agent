from __future__ import annotations

from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, Field, field_validator

from .common import ORMModel


class DocumentVersionResponse(ORMModel):
    id: UUID
    document_id: UUID
    version_number: int
    previous_version_id: UUID | None
    original_filename: str
    sha256: str
    status: str
    change_reason: str
    uploaded_by_user_id: UUID
    uploader_role_code: str
    created_at: datetime
    extracted_text_status: str | None = None
    indexed_at: datetime | None = None


class DocumentResponse(ORMModel):
    id: UUID
    tenant_id: UUID
    title: str
    document_type: str
    owner_user_id: UUID
    org_unit_id: UUID | None
    programme_id: UUID | None
    module_id: UUID | None
    visibility: str
    current_version_id: UUID | None
    created_at: datetime
    updated_at: datetime


class SingleUploadMetadata(BaseModel):
    title: str = Field(min_length=1, max_length=500)
    document_type: str = Field(min_length=1, max_length=100)
    change_reason: str = Field(min_length=1, max_length=2000)
    visibility: str = "private"
    existing_document_id: UUID | None = None
    org_unit_id: UUID | None = None
    programme_id: UUID | None = None
    module_id: UUID | None = None


class UploadResponse(BaseModel):
    document: DocumentResponse
    version: DocumentVersionResponse
    exact_duplicate: bool


class VersionHistoryResponse(BaseModel):
    document: DocumentResponse
    versions: list[DocumentVersionResponse]


class DocumentVersionTransitionRequest(BaseModel):
    to_status: str = Field(min_length=3, max_length=40)
    reason: str = Field(min_length=3, max_length=2000)

    @field_validator("to_status")
    @classmethod
    def validate_status(cls, value: str) -> str:
        allowed = {
            "working", "under_review", "approved", "published",
            "superseded", "archived", "rejected",
        }
        normalised = value.strip().lower()
        if normalised not in allowed:
            raise ValueError(f"Unsupported document version status: {normalised}")
        return normalised


class DocumentVersionTransitionResponse(ORMModel):
    id: UUID
    document_version_id: UUID
    from_status: str | None
    to_status: str
    changed_by_user_id: UUID
    changed_by_role_code: str
    reason: str
    transition_metadata: dict
    created_at: datetime
