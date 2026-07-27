from __future__ import annotations

from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, Field, model_validator

from .common import ORMModel


class ExternalAccessGrantCreate(BaseModel):
    external_user_id: UUID
    purpose: str = Field(min_length=1, max_length=2000)
    starts_at: datetime
    expires_at: datetime
    allowed_actions: list[str] = Field(min_length=1)
    resource_scope: dict

    @model_validator(mode="after")
    def validate_window(self) -> "ExternalAccessGrantCreate":
        if self.expires_at <= self.starts_at:
            raise ValueError("expires_at must be later than starts_at")
        if not self.resource_scope:
            raise ValueError("resource_scope is required")
        return self


class ExternalAccessGrantResponse(ORMModel):
    id: UUID
    tenant_id: UUID
    external_user_id: UUID
    granted_by_user_id: UUID
    purpose: str
    status: str
    starts_at: datetime
    expires_at: datetime
    allowed_actions: list[str]
    resource_scope: dict
    created_at: datetime


class ExternalAccessRevoke(BaseModel):
    reason: str = Field(min_length=3, max_length=2000)
