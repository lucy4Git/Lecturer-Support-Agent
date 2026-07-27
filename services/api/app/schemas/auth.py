from __future__ import annotations

from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, EmailStr, Field, SecretStr, model_validator


class LoginRequest(BaseModel):
    email: EmailStr
    password: SecretStr
    institution_id: UUID | None = None
    institution_slug: str | None = Field(default=None, min_length=2, max_length=80)
    role_code: str | None = Field(default=None, min_length=2, max_length=80)
    device_label: str | None = Field(default=None, max_length=180)
    mfa_code: str | None = Field(default=None, min_length=6, max_length=20)

    @model_validator(mode="after")
    def require_institution_selector(self) -> "LoginRequest":
        if not self.institution_id and not self.institution_slug:
            raise ValueError("institution_id or institution_slug is required")
        return self


class RefreshRequest(BaseModel):
    refresh_token: SecretStr


class LogoutRequest(BaseModel):
    refresh_token: SecretStr | None = None
    all_sessions: bool = False


class InvitationAcceptRequest(BaseModel):
    invitation_token: SecretStr
    given_name: str = Field(min_length=1, max_length=120)
    family_name: str = Field(min_length=1, max_length=120)
    password: SecretStr


class TokenResponse(BaseModel):
    access_token: str
    refresh_token: str
    token_type: str = "bearer"
    access_token_expires_at: datetime
    refresh_token_expires_at: datetime
    tenant_id: UUID
    user_id: UUID
    membership_id: UUID
    role_assignment_id: UUID
    role_code: str


class RoleOption(BaseModel):
    role_code: str
    role_name: str
    role_assignment_id: UUID
    scope_type: str | None = None
    scope_id: UUID | None = None


class LoginSelectionRequired(BaseModel):
    detail: str
    available_roles: list[RoleOption]


class InvitationAcceptedResponse(BaseModel):
    tenant_id: UUID
    user_id: UUID
    membership_id: UUID
    assigned_role_codes: list[str]
    message: str
