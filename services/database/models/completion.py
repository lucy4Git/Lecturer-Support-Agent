from __future__ import annotations

from datetime import datetime
from uuid import UUID

from sqlalchemy import Boolean, DateTime, ForeignKey, Index, Integer, String, Text, UniqueConstraint, Uuid
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from .base import Base, TenantOwnedMixin, TimestampMixin, UUIDPrimaryKeyMixin


class AccountChallenge(Base, UUIDPrimaryKeyMixin, TenantOwnedMixin, TimestampMixin):
    """Hashed, single-use identity challenge for reset, verification, MFA, or OIDC state."""

    __tablename__ = "account_challenges"
    __table_args__ = (
        UniqueConstraint("token_hash"),
        Index("ix_account_challenge_active", "tenant_id", "challenge_type", "status", "expires_at"),
        {"schema": "iam"},
    )

    user_id: Mapped[UUID | None] = mapped_column(ForeignKey("iam.users.id", ondelete="CASCADE"))
    challenge_type: Mapped[str] = mapped_column(String(60), nullable=False)
    token_hash: Mapped[str] = mapped_column(String(64), nullable=False)
    status: Mapped[str] = mapped_column(String(30), default="pending", nullable=False)
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    consumed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    requested_ip_hash: Mapped[str | None] = mapped_column(String(64))
    metadata_payload: Mapped[dict] = mapped_column("metadata", JSONB, default=dict, nullable=False)


class MFADevice(Base, UUIDPrimaryKeyMixin, TenantOwnedMixin, TimestampMixin):
    __tablename__ = "mfa_devices"
    __table_args__ = (
        Index("ix_mfa_device_user", "tenant_id", "user_id", "status"),
        {"schema": "iam"},
    )

    user_id: Mapped[UUID] = mapped_column(ForeignKey("iam.users.id", ondelete="CASCADE"), nullable=False)
    device_type: Mapped[str] = mapped_column(String(40), default="totp", nullable=False)
    label: Mapped[str] = mapped_column(String(160), nullable=False)
    secret_ciphertext: Mapped[str] = mapped_column(Text, nullable=False)
    status: Mapped[str] = mapped_column(String(30), default="pending", nullable=False)
    confirmed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    last_used_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    disabled_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))


class MFARecoveryCode(Base, UUIDPrimaryKeyMixin, TenantOwnedMixin, TimestampMixin):
    __tablename__ = "mfa_recovery_codes"
    __table_args__ = (
        UniqueConstraint("tenant_id", "device_id", "code_hash"),
        Index("ix_mfa_recovery_unused", "tenant_id", "device_id", "used_at"),
        {"schema": "iam"},
    )

    device_id: Mapped[UUID] = mapped_column(ForeignKey("iam.mfa_devices.id", ondelete="CASCADE"), nullable=False)
    code_hash: Mapped[str] = mapped_column(String(64), nullable=False)
    used_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))


class SSOConnection(Base, UUIDPrimaryKeyMixin, TenantOwnedMixin, TimestampMixin):
    __tablename__ = "sso_connections"
    __table_args__ = (
        UniqueConstraint("tenant_id", "code"),
        Index("ix_sso_connection_enabled", "tenant_id", "is_enabled"),
        {"schema": "iam"},
    )

    code: Mapped[str] = mapped_column(String(100), nullable=False)
    display_name: Mapped[str] = mapped_column(String(200), nullable=False)
    protocol: Mapped[str] = mapped_column(String(30), default="oidc", nullable=False)
    issuer_url: Mapped[str] = mapped_column(String(1000), nullable=False)
    client_id: Mapped[str] = mapped_column(String(500), nullable=False)
    client_secret_reference: Mapped[str | None] = mapped_column(String(300))
    scopes: Mapped[list] = mapped_column(JSONB, default=lambda: ["openid", "profile", "email"], nullable=False)
    claim_mapping: Mapped[dict] = mapped_column(JSONB, default=dict, nullable=False)
    default_role_code: Mapped[str | None] = mapped_column(String(80))
    is_enabled: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    metadata_payload: Mapped[dict] = mapped_column("metadata", JSONB, default=dict, nullable=False)


class FederatedIdentity(Base, UUIDPrimaryKeyMixin, TenantOwnedMixin, TimestampMixin):
    __tablename__ = "federated_identities"
    __table_args__ = (
        UniqueConstraint("tenant_id", "sso_connection_id", "external_subject"),
        Index("ix_federated_identity_user", "tenant_id", "user_id"),
        {"schema": "iam"},
    )

    user_id: Mapped[UUID] = mapped_column(ForeignKey("iam.users.id", ondelete="CASCADE"), nullable=False)
    sso_connection_id: Mapped[UUID] = mapped_column(ForeignKey("iam.sso_connections.id", ondelete="CASCADE"), nullable=False)
    external_subject: Mapped[str] = mapped_column(String(500), nullable=False)
    external_email: Mapped[str | None] = mapped_column(String(320))
    last_claims: Mapped[dict] = mapped_column(JSONB, default=dict, nullable=False)
    last_login_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))


class OutboundMessage(Base, UUIDPrimaryKeyMixin, TenantOwnedMixin, TimestampMixin):
    __tablename__ = "outbound_messages"
    __table_args__ = (
        UniqueConstraint("tenant_id", "idempotency_key"),
        Index("ix_outbound_message_status", "tenant_id", "channel", "status", "created_at"),
        {"schema": "governance"},
    )

    channel: Mapped[str] = mapped_column(String(30), default="email", nullable=False)
    template_code: Mapped[str] = mapped_column(String(100), nullable=False)
    recipient_address: Mapped[str] = mapped_column(String(500), nullable=False)
    recipient_user_id: Mapped[UUID | None] = mapped_column(ForeignKey("iam.users.id", ondelete="SET NULL"))
    subject: Mapped[str] = mapped_column(String(500), nullable=False)
    body_text: Mapped[str] = mapped_column(Text, nullable=False)
    body_html: Mapped[str | None] = mapped_column(Text)
    status: Mapped[str] = mapped_column(String(30), default="queued", nullable=False)
    provider: Mapped[str | None] = mapped_column(String(80))
    provider_message_id: Mapped[str | None] = mapped_column(String(300))
    idempotency_key: Mapped[str] = mapped_column(String(240), nullable=False)
    attempt_count: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    scheduled_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    sent_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    failed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    last_error: Mapped[str | None] = mapped_column(Text)
    metadata_payload: Mapped[dict] = mapped_column("metadata", JSONB, default=dict, nullable=False)


class IntegrationConnection(Base, UUIDPrimaryKeyMixin, TenantOwnedMixin, TimestampMixin):
    __tablename__ = "integration_connections"
    __table_args__ = (
        UniqueConstraint("tenant_id", "code"),
        Index("ix_integration_connection_type", "tenant_id", "integration_type", "status"),
        {"schema": "governance"},
    )

    code: Mapped[str] = mapped_column(String(100), nullable=False)
    display_name: Mapped[str] = mapped_column(String(200), nullable=False)
    integration_type: Mapped[str] = mapped_column(String(60), nullable=False)
    base_url: Mapped[str | None] = mapped_column(String(1200))
    authentication_type: Mapped[str] = mapped_column(String(50), default="oauth2", nullable=False)
    secret_reference: Mapped[str | None] = mapped_column(String(300))
    status: Mapped[str] = mapped_column(String(30), default="configured", nullable=False)
    capabilities: Mapped[list] = mapped_column(JSONB, default=list, nullable=False)
    configuration: Mapped[dict] = mapped_column(JSONB, default=dict, nullable=False)
    last_tested_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    last_test_status: Mapped[str | None] = mapped_column(String(30))


class IntegrationSyncRun(Base, UUIDPrimaryKeyMixin, TenantOwnedMixin, TimestampMixin):
    __tablename__ = "integration_sync_runs"
    __table_args__ = (
        Index("ix_integration_sync_run", "tenant_id", "connection_id", "status", "created_at"),
        {"schema": "operations"},
    )

    connection_id: Mapped[UUID] = mapped_column(ForeignKey("governance.integration_connections.id", ondelete="CASCADE"), nullable=False)
    sync_type: Mapped[str] = mapped_column(String(80), nullable=False)
    direction: Mapped[str] = mapped_column(String(20), default="inbound", nullable=False)
    status: Mapped[str] = mapped_column(String(30), default="queued", nullable=False)
    requested_by_user_id: Mapped[UUID | None] = mapped_column(ForeignKey("iam.users.id"))
    started_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    cursor: Mapped[str | None] = mapped_column(String(1000))
    records_read: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    records_written: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    records_failed: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    result_payload: Mapped[dict] = mapped_column(JSONB, default=dict, nullable=False)
    error_detail: Mapped[str | None] = mapped_column(Text)


class ExternalRecordMapping(Base, UUIDPrimaryKeyMixin, TenantOwnedMixin, TimestampMixin):
    __tablename__ = "external_record_mappings"
    __table_args__ = (
        UniqueConstraint("tenant_id", "connection_id", "external_type", "external_id"),
        Index("ix_external_record_local", "tenant_id", "local_type", "local_id"),
        {"schema": "governance"},
    )

    connection_id: Mapped[UUID] = mapped_column(ForeignKey("governance.integration_connections.id", ondelete="CASCADE"), nullable=False)
    external_type: Mapped[str] = mapped_column(String(80), nullable=False)
    external_id: Mapped[str] = mapped_column(String(500), nullable=False)
    local_type: Mapped[str] = mapped_column(String(80), nullable=False)
    local_id: Mapped[UUID] = mapped_column(Uuid(as_uuid=True), nullable=False)
    external_version: Mapped[str | None] = mapped_column(String(300))
    mapping_metadata: Mapped[dict] = mapped_column("metadata", JSONB, default=dict, nullable=False)


class LegalHold(Base, UUIDPrimaryKeyMixin, TenantOwnedMixin, TimestampMixin):
    __tablename__ = "legal_holds"
    __table_args__ = (
        Index("ix_legal_hold_resource", "tenant_id", "resource_type", "resource_id", "released_at"),
        {"schema": "privacy"},
    )

    resource_type: Mapped[str] = mapped_column(String(100), nullable=False)
    resource_id: Mapped[UUID | None] = mapped_column(Uuid(as_uuid=True))
    scope_type: Mapped[str] = mapped_column(String(80), nullable=False)
    scope_id: Mapped[UUID | None] = mapped_column(Uuid(as_uuid=True))
    reason: Mapped[str] = mapped_column(Text, nullable=False)
    legal_basis: Mapped[str | None] = mapped_column(Text)
    placed_by_user_id: Mapped[UUID] = mapped_column(ForeignKey("iam.users.id"), nullable=False)
    placed_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    review_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    released_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    released_by_user_id: Mapped[UUID | None] = mapped_column(ForeignKey("iam.users.id"))
    release_reason: Mapped[str | None] = mapped_column(Text)


class DeletionRequest(Base, UUIDPrimaryKeyMixin, TenantOwnedMixin, TimestampMixin):
    __tablename__ = "deletion_requests"
    __table_args__ = (
        Index("ix_deletion_request_status", "tenant_id", "status", "created_at"),
        {"schema": "privacy"},
    )

    resource_type: Mapped[str] = mapped_column(String(100), nullable=False)
    resource_id: Mapped[UUID] = mapped_column(Uuid(as_uuid=True), nullable=False)
    requested_by_user_id: Mapped[UUID] = mapped_column(ForeignKey("iam.users.id"), nullable=False)
    reason: Mapped[str] = mapped_column(Text, nullable=False)
    status: Mapped[str] = mapped_column(String(30), default="preview", nullable=False)
    legal_hold_blocked: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    approved_by_user_id: Mapped[UUID | None] = mapped_column(ForeignKey("iam.users.id"))
    approved_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    manifest: Mapped[dict] = mapped_column(JSONB, default=dict, nullable=False)
    error_detail: Mapped[str | None] = mapped_column(Text)


class DeletionAction(Base, UUIDPrimaryKeyMixin, TenantOwnedMixin, TimestampMixin):
    __tablename__ = "deletion_actions"
    __table_args__ = (
        Index("ix_deletion_action_request", "tenant_id", "deletion_request_id", "sequence_number"),
        {"schema": "privacy"},
    )

    deletion_request_id: Mapped[UUID] = mapped_column(ForeignKey("privacy.deletion_requests.id", ondelete="CASCADE"), nullable=False)
    sequence_number: Mapped[int] = mapped_column(Integer, nullable=False)
    component: Mapped[str] = mapped_column(String(80), nullable=False)
    action: Mapped[str] = mapped_column(String(80), nullable=False)
    status: Mapped[str] = mapped_column(String(30), default="planned", nullable=False)
    target_reference: Mapped[str | None] = mapped_column(String(1200))
    evidence_sha256: Mapped[str | None] = mapped_column(String(64))
    completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    error_detail: Mapped[str | None] = mapped_column(Text)


class UserFeedback(Base, UUIDPrimaryKeyMixin, TenantOwnedMixin, TimestampMixin):
    __tablename__ = "user_feedback"
    __table_args__ = (
        Index("ix_user_feedback_target", "tenant_id", "target_type", "target_id", "created_at"),
        {"schema": "analytics"},
    )

    user_id: Mapped[UUID] = mapped_column(ForeignKey("iam.users.id"), nullable=False)
    target_type: Mapped[str] = mapped_column(String(80), nullable=False)
    target_id: Mapped[UUID] = mapped_column(Uuid(as_uuid=True), nullable=False)
    rating: Mapped[int | None] = mapped_column(Integer)
    feedback_type: Mapped[str] = mapped_column(String(80), nullable=False)
    comment: Mapped[str | None] = mapped_column(Text)
    issue_codes: Mapped[list] = mapped_column(JSONB, default=list, nullable=False)
    consent_for_research: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    status: Mapped[str] = mapped_column(String(30), default="submitted", nullable=False)


class EvaluationCampaign(Base, UUIDPrimaryKeyMixin, TenantOwnedMixin, TimestampMixin):
    __tablename__ = "evaluation_campaigns"
    __table_args__ = (
        UniqueConstraint("tenant_id", "code"),
        {"schema": "analytics"},
    )

    code: Mapped[str] = mapped_column(String(100), nullable=False)
    name: Mapped[str] = mapped_column(String(300), nullable=False)
    description: Mapped[str | None] = mapped_column(Text)
    status: Mapped[str] = mapped_column(String(30), default="draft", nullable=False)
    starts_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    ends_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    instrument_definition: Mapped[dict] = mapped_column(JSONB, default=dict, nullable=False)
    created_by_user_id: Mapped[UUID] = mapped_column(ForeignKey("iam.users.id"), nullable=False)


class EvaluationResponse(Base, UUIDPrimaryKeyMixin, TenantOwnedMixin, TimestampMixin):
    __tablename__ = "evaluation_responses"
    __table_args__ = (
        UniqueConstraint("tenant_id", "campaign_id", "participant_user_id", "task_reference"),
        {"schema": "analytics"},
    )

    campaign_id: Mapped[UUID] = mapped_column(ForeignKey("analytics.evaluation_campaigns.id", ondelete="CASCADE"), nullable=False)
    participant_user_id: Mapped[UUID | None] = mapped_column(ForeignKey("iam.users.id"))
    task_reference: Mapped[str] = mapped_column(String(300), nullable=False)
    role_code: Mapped[str | None] = mapped_column(String(80))
    responses: Mapped[dict] = mapped_column(JSONB, default=dict, nullable=False)
    computed_scores: Mapped[dict] = mapped_column(JSONB, default=dict, nullable=False)
    submitted_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)


class DatasetSourceRecord(Base, UUIDPrimaryKeyMixin, TenantOwnedMixin, TimestampMixin):
    __tablename__ = "dataset_source_records"
    __table_args__ = (
        UniqueConstraint("tenant_id", "source_key"),
        Index("ix_dataset_source_status", "tenant_id", "approval_status", "intended_use"),
        {"schema": "governance"},
    )

    source_key: Mapped[str] = mapped_column(String(160), nullable=False)
    title: Mapped[str] = mapped_column(String(500), nullable=False)
    provider: Mapped[str] = mapped_column(String(200), nullable=False)
    canonical_url: Mapped[str] = mapped_column(String(1500), nullable=False)
    licence_code: Mapped[str | None] = mapped_column(String(100))
    licence_url: Mapped[str | None] = mapped_column(String(1500))
    commercial_use_allowed: Mapped[bool | None] = mapped_column(Boolean)
    ai_training_allowed: Mapped[bool | None] = mapped_column(Boolean)
    intended_use: Mapped[str] = mapped_column(String(60), nullable=False)
    disciplines: Mapped[list] = mapped_column(JSONB, default=list, nullable=False)
    approval_status: Mapped[str] = mapped_column(String(30), default="candidate", nullable=False)
    approved_by_user_id: Mapped[UUID | None] = mapped_column(ForeignKey("iam.users.id"))
    approved_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    provenance: Mapped[dict] = mapped_column(JSONB, default=dict, nullable=False)


class DatasetAcquisitionRun(Base, UUIDPrimaryKeyMixin, TenantOwnedMixin, TimestampMixin):
    __tablename__ = "dataset_acquisition_runs"
    __table_args__ = (
        Index("ix_dataset_acquisition_run", "tenant_id", "status", "created_at"),
        {"schema": "operations"},
    )

    source_record_id: Mapped[UUID] = mapped_column(ForeignKey("governance.dataset_source_records.id"), nullable=False)
    status: Mapped[str] = mapped_column(String(30), default="requested", nullable=False)
    requested_by_user_id: Mapped[UUID] = mapped_column(ForeignKey("iam.users.id"), nullable=False)
    started_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    records_acquired: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    checksum_manifest: Mapped[dict] = mapped_column(JSONB, default=dict, nullable=False)
    storage_prefix: Mapped[str | None] = mapped_column(String(1200))
    error_detail: Mapped[str | None] = mapped_column(Text)
