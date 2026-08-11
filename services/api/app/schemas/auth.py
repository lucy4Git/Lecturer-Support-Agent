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


class InstitutionalAccessRequestCreate(BaseModel):
    institution_slug: str = Field(min_length=2, max_length=80)
    email: EmailStr
    given_name: str = Field(min_length=1, max_length=120)
    family_name: str = Field(min_length=1, max_length=120)
    position_title: str | None = Field(default=None, max_length=180)
    requested_role_code: str | None = Field(default=None, max_length=80)
    request_message: str | None = Field(default=None, max_length=4000)


class InstitutionalAccessRequestResponse(BaseModel):
    request_id: UUID
    status: str
    message: str


class InstitutionSummary(BaseModel):
    id: UUID
    display_name: str
    institution_type: str
    country_code: str | None = None


class DirectRegistrationRequest(BaseModel):
    institution_id: UUID
    email: EmailStr
    given_name: str = Field(min_length=1, max_length=120)
    family_name: str = Field(min_length=1, max_length=120)
    password: SecretStr
    role_code: str = Field(min_length=2, max_length=80)

    @model_validator(mode="after")
    def validate_role_code(self) -> "DirectRegistrationRequest":
        allowed = {
            "institution_administrator", "head_of_department", "lecturer",
            "module_coordinator", "programme_coordinator",
            "internal_moderator", "external_moderator", "external_reviewer",
        }
        if self.role_code not in allowed:
            raise ValueError(f"role_code must be one of: {', '.join(sorted(allowed))}")
        return self


class DirectRegistrationResponse(BaseModel):
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
    message: str


class DirectPasswordResetRequest(BaseModel):
    email: EmailStr
    new_password: SecretStr
    confirm_password: SecretStr

    @model_validator(mode="after")
    def passwords_match(self) -> "DirectPasswordResetRequest":
        if self.new_password.get_secret_value() != self.confirm_password.get_secret_value():
            raise ValueError("Passwords do not match.")
        return self
