from __future__ import annotations

from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, EmailStr, Field, SecretStr, model_validator

from .common import ORMModel


class PasswordResetRequest(BaseModel):
    email: EmailStr
    institution_id: UUID | None = None
    institution_slug: str | None = Field(default=None, min_length=2, max_length=80)

    @model_validator(mode="after")
    def require_tenant(self) -> "PasswordResetRequest":
        if not self.institution_id and not self.institution_slug:
            raise ValueError("institution_id or institution_slug is required")
        return self


class PasswordResetConfirm(BaseModel):
    reset_token: SecretStr
    new_password: SecretStr


class EmailVerificationConfirm(BaseModel):
    verification_token: SecretStr


class MFAEnrolRequest(BaseModel):
    label: str = Field(default="Authenticator", min_length=2, max_length=160)


class MFAEnrolResponse(BaseModel):
    device_id: UUID
    secret: str
    provisioning_uri: str
    recovery_codes: list[str]


class MFAConfirmRequest(BaseModel):
    code: str = Field(min_length=6, max_length=12)


class MFADisableRequest(BaseModel):
    code: str = Field(min_length=6, max_length=20)
    reason: str = Field(min_length=3, max_length=1000)


class SSOConnectionCreate(BaseModel):
    code: str = Field(pattern=r"^[a-z0-9_-]+$", min_length=2, max_length=100)
    display_name: str = Field(min_length=2, max_length=200)
    protocol: str = Field(default="oidc", pattern="^(oidc|saml)$")
    issuer_url: str = Field(min_length=8, max_length=1000)
    client_id: str = Field(min_length=2, max_length=500)
    client_secret_reference: str | None = Field(default=None, max_length=300)
    scopes: list[str] = Field(default_factory=lambda: ["openid", "profile", "email"])
    claim_mapping: dict = Field(default_factory=dict)
    default_role_code: str | None = Field(default=None, max_length=80)
    is_enabled: bool = True
    redirect_uris: list[str] = Field(default_factory=list, max_length=20)
    allow_account_linking_by_verified_email: bool = False


class SSOConnectionResponse(ORMModel):
    id: UUID
    tenant_id: UUID
    code: str
    display_name: str
    protocol: str
    issuer_url: str
    client_id: str
    client_secret_reference: str | None
    scopes: list
    claim_mapping: dict
    default_role_code: str | None
    is_enabled: bool
    created_at: datetime


class IntegrationConnectionCreate(BaseModel):
    code: str = Field(pattern=r"^[a-z0-9_-]+$", min_length=2, max_length=100)
    display_name: str = Field(min_length=2, max_length=200)
    integration_type: str = Field(pattern="^(canvas|moodle|oneroster_csv|oneroster_rest|generic_rest)$")
    base_url: str | None = Field(default=None, max_length=1200)
    authentication_type: str = Field(default="oauth2", max_length=50)
    secret_reference: str | None = Field(default=None, max_length=300)
    capabilities: list[str] = Field(default_factory=list)
    configuration: dict = Field(default_factory=dict)


class IntegrationConnectionResponse(ORMModel):
    id: UUID
    tenant_id: UUID
    code: str
    display_name: str
    integration_type: str
    base_url: str | None
    authentication_type: str
    secret_reference: str | None
    status: str
    capabilities: list
    configuration: dict
    last_tested_at: datetime | None
    last_test_status: str | None
    created_at: datetime


class IntegrationSyncRequest(BaseModel):
    sync_type: str = Field(min_length=2, max_length=80)
    direction: str = Field(default="inbound", pattern="^(inbound|outbound|bidirectional)$")
    cursor: str | None = Field(default=None, max_length=1000)


class LegalHoldCreate(BaseModel):
    resource_type: str = Field(min_length=2, max_length=100)
    resource_id: UUID | None = None
    scope_type: str = Field(default="institution", min_length=2, max_length=80)
    scope_id: UUID | None = None
    reason: str = Field(min_length=10, max_length=5000)
    legal_basis: str | None = Field(default=None, max_length=5000)
    review_at: datetime | None = None


class LegalHoldRelease(BaseModel):
    reason: str = Field(min_length=10, max_length=5000)


class LegalHoldResponse(ORMModel):
    id: UUID
    tenant_id: UUID
    resource_type: str
    resource_id: UUID | None
    scope_type: str
    scope_id: UUID | None
    reason: str
    legal_basis: str | None
    placed_by_user_id: UUID
    placed_at: datetime
    review_at: datetime | None
    released_at: datetime | None


class DeletionRequestCreate(BaseModel):
    resource_type: str = Field(min_length=2, max_length=100)
    resource_id: UUID
    reason: str = Field(min_length=10, max_length=5000)


class DeletionApprovalRequest(BaseModel):
    approve: bool
    reason: str = Field(min_length=5, max_length=5000)


class DeletionRequestResponse(ORMModel):
    id: UUID
    tenant_id: UUID
    resource_type: str
    resource_id: UUID
    requested_by_user_id: UUID
    reason: str
    status: str
    legal_hold_blocked: bool
    approved_by_user_id: UUID | None
    approved_at: datetime | None
    completed_at: datetime | None
    manifest: dict
    created_at: datetime


class UserFeedbackCreate(BaseModel):
    target_type: str = Field(min_length=2, max_length=80)
    target_id: UUID
    rating: int | None = Field(default=None, ge=1, le=5)
    feedback_type: str = Field(default="quality", min_length=2, max_length=80)
    comment: str | None = Field(default=None, max_length=5000)
    issue_codes: list[str] = Field(default_factory=list, max_length=20)
    consent_for_research: bool = False


class UserFeedbackResponse(ORMModel):
    id: UUID
    tenant_id: UUID
    user_id: UUID
    target_type: str
    target_id: UUID
    rating: int | None
    feedback_type: str
    comment: str | None
    issue_codes: list
    consent_for_research: bool
    status: str
    created_at: datetime


class EvaluationCampaignCreate(BaseModel):
    code: str = Field(pattern=r"^[a-z0-9_-]+$", min_length=2, max_length=100)
    name: str = Field(min_length=2, max_length=300)
    description: str | None = Field(default=None, max_length=5000)
    starts_at: datetime | None = None
    ends_at: datetime | None = None
    instrument_definition: dict = Field(default_factory=dict)


class EvaluationResponseCreate(BaseModel):
    task_reference: str = Field(min_length=2, max_length=300)
    responses: dict


class DatasetSourceCreate(BaseModel):
    source_key: str = Field(pattern=r"^[a-z0-9_.-]+$", min_length=2, max_length=160)
    title: str = Field(min_length=2, max_length=500)
    provider: str = Field(min_length=2, max_length=200)
    canonical_url: str = Field(min_length=8, max_length=1500)
    licence_code: str | None = Field(default=None, max_length=100)
    licence_url: str | None = Field(default=None, max_length=1500)
    commercial_use_allowed: bool | None = None
    ai_training_allowed: bool | None = None
    intended_use: str = Field(pattern="^(metadata|retrieval|evaluation|adaptation)$")
    disciplines: list[str] = Field(default_factory=list)
    provenance: dict = Field(default_factory=dict)


class DatasetApprovalRequest(BaseModel):
    approve: bool
    review_note: str = Field(min_length=5, max_length=5000)


class DatasetAcquisitionRequest(BaseModel):
    limit: int = Field(default=100, ge=1, le=10000)
    query: str | None = Field(default=None, max_length=1000)

class SSOStartRequest(BaseModel):
    institution_id: UUID | None = None
    institution_slug: str | None = Field(default=None, min_length=2, max_length=80)
    connection_code: str = Field(min_length=2, max_length=100)
    redirect_uri: str = Field(min_length=8, max_length=1200)

    @model_validator(mode="after")
    def require_institution(self) -> "SSOStartRequest":
        if not self.institution_id and not self.institution_slug:
            raise ValueError("institution_id or institution_slug is required")
        return self


class SSOStartResponse(BaseModel):
    authorization_url: str
    state: str
    expires_at: datetime


class SSOCallbackRequest(BaseModel):
    state: SecretStr
    code: SecretStr


class SSOCallbackResponse(BaseModel):
    handoff_token: str
    available_roles: list[dict]
    expires_at: datetime


class SSOExchangeRequest(BaseModel):
    handoff_token: SecretStr
    role_code: str = Field(min_length=2, max_length=80)
    device_label: str | None = Field(default=None, max_length=180)
