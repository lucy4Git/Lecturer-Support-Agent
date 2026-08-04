from __future__ import annotations

from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, ConfigDict, EmailStr, Field, model_validator

from .common import ORMModel


class InvitationRoleRequest(BaseModel):
    role_code: str = Field(min_length=2, max_length=80)
    scope_type: str = Field(default="institution", min_length=2, max_length=60)
    scope_id: UUID | None = None
    include_descendants: bool = False
    constraints: dict = Field(default_factory=dict)


class UserInvitationCreate(BaseModel):
    email: EmailStr
    institutional_identifier: str | None = Field(default=None, max_length=100)
    position_title: str | None = Field(default=None, max_length=180)
    invitation_message: str | None = Field(default=None, max_length=2000)
    roles: list[InvitationRoleRequest] = Field(min_length=1, max_length=10)


class UserInvitationResponse(ORMModel):
    id: UUID
    tenant_id: UUID
    email: str
    status: str
    expires_at: datetime
    created_at: datetime
    invitation_url: str | None = None
    delivery_status: str = "pending_email_delivery"


class MembershipStatusUpdate(BaseModel):
    status: str = Field(pattern="^(active|suspended|deactivated)$")
    reason: str | None = Field(default=None, max_length=1000)


class UserSummary(BaseModel):
    user_id: UUID
    membership_id: UUID
    email: str
    display_name: str
    institutional_identifier: str | None
    position_title: str | None
    membership_status: str
    is_active: bool
    created_at: datetime


class RoleAssignmentCreate(BaseModel):
    user_id: UUID
    role_code: str = Field(min_length=2, max_length=80)
    scope_type: str = Field(default="institution", min_length=2, max_length=60)
    scope_id: UUID | None = None
    include_descendants: bool = False
    valid_from: datetime
    valid_until: datetime | None = None
    reason: str | None = Field(default=None, max_length=1000)

    @model_validator(mode="after")
    def validate_period(self) -> "RoleAssignmentCreate":
        if self.valid_until is not None and self.valid_until <= self.valid_from:
            raise ValueError("valid_until must be later than valid_from")
        return self


class RoleAssignmentResponse(ORMModel):
    id: UUID
    tenant_id: UUID
    user_id: UUID
    role_id: UUID
    access_scope_id: UUID | None
    assigned_by_user_id: UUID
    valid_from: datetime
    valid_until: datetime | None
    revoked_at: datetime | None
    reason: str | None
    created_at: datetime


class PositionDefinitionCreate(BaseModel):
    code: str = Field(min_length=2, max_length=100, pattern=r"^[a-z0-9_-]+$")
    label: str = Field(min_length=2, max_length=180)
    category: str = Field(default="academic", min_length=2, max_length=80)
    description: str | None = Field(default=None, max_length=2000)
    attributes: dict = Field(default_factory=dict)


class PositionDefinitionResponse(ORMModel):
    id: UUID
    tenant_id: UUID
    code: str
    label: str
    category: str
    description: str | None
    is_active: bool
    attributes: dict
    created_at: datetime


class MembershipPositionCreate(BaseModel):
    membership_id: UUID
    position_definition_id: UUID
    organisational_unit_id: UUID | None = None
    is_primary: bool = False
    valid_from: datetime
    valid_until: datetime | None = None

    @model_validator(mode="after")
    def validate_period(self) -> "MembershipPositionCreate":
        if self.valid_until is not None and self.valid_until <= self.valid_from:
            raise ValueError("valid_until must be later than valid_from")
        return self


class MembershipPositionResponse(ORMModel):
    id: UUID
    tenant_id: UUID
    membership_id: UUID
    position_definition_id: UUID
    organisational_unit_id: UUID | None
    is_primary: bool
    valid_from: datetime
    valid_until: datetime | None
    created_at: datetime

class AccessRequestSummary(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    tenant_id: UUID
    email: str
    given_name: str
    family_name: str
    position_title: str | None
    requested_role_code: str | None
    request_message: str | None
    status: str
    created_at: datetime
    reviewed_at: datetime | None
    decision_reason: str | None


class AccessRequestDecision(BaseModel):
    status: str = Field(pattern="^(approved|rejected|needs_information)$")
    decision_reason: str | None = Field(default=None, max_length=2000)
