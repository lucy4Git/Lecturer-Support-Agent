from __future__ import annotations

from datetime import datetime
from uuid import UUID

from sqlalchemy import (
    Boolean,
    DateTime,
    ForeignKey,
    Index,
    Integer,
    String,
    Text,
    UniqueConstraint,
    Uuid,
)
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from .base import Base, TenantOwnedMixin, TimestampMixin, UUIDPrimaryKeyMixin
from .enums import AuthSessionStatus, InvitationStatus, MembershipStatus


class User(Base, UUIDPrimaryKeyMixin, TimestampMixin):
    __tablename__ = "users"
    __table_args__ = (UniqueConstraint("email_normalized"), {"schema": "iam"})

    email: Mapped[str] = mapped_column(String(320), nullable=False)
    email_normalized: Mapped[str] = mapped_column(String(320), nullable=False)
    given_name: Mapped[str | None] = mapped_column(String(120), nullable=True)
    family_name: Mapped[str | None] = mapped_column(String(120), nullable=True)
    display_name: Mapped[str | None] = mapped_column(String(255), nullable=True)
    identity_provider: Mapped[str] = mapped_column(String(80), default="local", nullable=False)
    external_subject: Mapped[str | None] = mapped_column(String(255))
    is_platform_operator: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    last_login_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    profile: Mapped[dict] = mapped_column(JSONB, default=dict, nullable=False)


class PasswordCredential(Base, UUIDPrimaryKeyMixin, TimestampMixin):
    """Local credential record.

    Password hashes are Argon2id strings. Plaintext passwords, password hints,
    reset tokens, and API credentials are never stored in this table.
    """

    __tablename__ = "password_credentials"
    __table_args__ = (UniqueConstraint("user_id"), {"schema": "iam"})

    user_id: Mapped[UUID] = mapped_column(
        ForeignKey("iam.users.id", ondelete="CASCADE"), nullable=False
    )
    password_hash: Mapped[str] = mapped_column(Text, nullable=False)
    password_version: Mapped[int] = mapped_column(Integer, default=1, nullable=False)
    must_change_password: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    failed_attempts: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    locked_until: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    last_failed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    password_changed_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)


class Membership(Base, UUIDPrimaryKeyMixin, TenantOwnedMixin, TimestampMixin):
    __tablename__ = "memberships"
    __table_args__ = (
        UniqueConstraint("tenant_id", "user_id"),
        Index("ix_membership_status", "tenant_id", "status"),
        {"schema": "iam"},
    )

    user_id: Mapped[UUID] = mapped_column(
        ForeignKey("iam.users.id", ondelete="RESTRICT"), nullable=False
    )
    institutional_identifier: Mapped[str | None] = mapped_column(String(100))
    position_title: Mapped[str | None] = mapped_column(String(180))
    status: Mapped[str] = mapped_column(
        String(30), default=MembershipStatus.INVITED.value, nullable=False
    )
    joined_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    suspended_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    deactivated_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    deactivation_reason: Mapped[str | None] = mapped_column(Text)


class Role(Base, UUIDPrimaryKeyMixin, TimestampMixin):
    __tablename__ = "roles"
    __table_args__ = (UniqueConstraint("code"), {"schema": "iam"})

    code: Mapped[str] = mapped_column(String(80), nullable=False)
    name: Mapped[str] = mapped_column(String(150), nullable=False)
    description: Mapped[str] = mapped_column(Text, nullable=False)
    is_system_role: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    is_external: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)


class Permission(Base, UUIDPrimaryKeyMixin, TimestampMixin):
    __tablename__ = "permissions"
    __table_args__ = (UniqueConstraint("code"), {"schema": "iam"})

    code: Mapped[str] = mapped_column(String(120), nullable=False)
    resource: Mapped[str] = mapped_column(String(80), nullable=False)
    action: Mapped[str] = mapped_column(String(80), nullable=False)
    description: Mapped[str] = mapped_column(Text, nullable=False)
    risk_level: Mapped[str] = mapped_column(String(20), default="normal", nullable=False)


class RolePermission(Base):
    __tablename__ = "role_permissions"
    __table_args__ = ({"schema": "iam"},)

    role_id: Mapped[UUID] = mapped_column(
        ForeignKey("iam.roles.id", ondelete="CASCADE"), primary_key=True
    )
    permission_id: Mapped[UUID] = mapped_column(
        ForeignKey("iam.permissions.id", ondelete="CASCADE"), primary_key=True
    )


class AccessScope(Base, UUIDPrimaryKeyMixin, TenantOwnedMixin, TimestampMixin):
    __tablename__ = "access_scopes"
    __table_args__ = (
        Index("ix_access_scope_resource", "tenant_id", "scope_type", "scope_id"),
        {"schema": "iam"},
    )

    scope_type: Mapped[str] = mapped_column(String(60), nullable=False)
    scope_id: Mapped[UUID | None] = mapped_column(Uuid(as_uuid=True))
    include_descendants: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    constraints: Mapped[dict] = mapped_column(JSONB, default=dict, nullable=False)


class RoleAssignment(Base, UUIDPrimaryKeyMixin, TenantOwnedMixin, TimestampMixin):
    __tablename__ = "role_assignments"
    __table_args__ = (
        Index("ix_role_assignment_active", "tenant_id", "user_id", "valid_from", "valid_until"),
        {"schema": "iam"},
    )

    user_id: Mapped[UUID] = mapped_column(
        ForeignKey("iam.users.id", ondelete="RESTRICT"), nullable=False
    )
    role_id: Mapped[UUID] = mapped_column(
        ForeignKey("iam.roles.id", ondelete="RESTRICT"), nullable=False
    )
    access_scope_id: Mapped[UUID | None] = mapped_column(
        ForeignKey("iam.access_scopes.id", ondelete="RESTRICT")
    )
    assigned_by_user_id: Mapped[UUID] = mapped_column(
        ForeignKey("iam.users.id", ondelete="RESTRICT"), nullable=False
    )
    valid_from: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    valid_until: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    revoked_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    revoked_by_user_id: Mapped[UUID | None] = mapped_column(ForeignKey("iam.users.id"))
    reason: Mapped[str | None] = mapped_column(Text)


class PositionDefinition(Base, UUIDPrimaryKeyMixin, TenantOwnedMixin, TimestampMixin):
    """Institution-defined position label independent of security roles."""

    __tablename__ = "position_definitions"
    __table_args__ = (
        UniqueConstraint("tenant_id", "code"),
        Index("ix_position_definition_active", "tenant_id", "is_active"),
        {"schema": "iam"},
    )

    code: Mapped[str] = mapped_column(String(100), nullable=False)
    label: Mapped[str] = mapped_column(String(180), nullable=False)
    category: Mapped[str] = mapped_column(String(80), default="academic", nullable=False)
    description: Mapped[str | None] = mapped_column(Text)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    attributes: Mapped[dict] = mapped_column(JSONB, default=dict, nullable=False)


class MembershipPosition(Base, UUIDPrimaryKeyMixin, TenantOwnedMixin, TimestampMixin):
    __tablename__ = "membership_positions"
    __table_args__ = (
        Index("ix_membership_position_active", "tenant_id", "membership_id", "valid_until"),
        {"schema": "iam"},
    )

    membership_id: Mapped[UUID] = mapped_column(
        ForeignKey("iam.memberships.id", ondelete="CASCADE"), nullable=False
    )
    position_definition_id: Mapped[UUID] = mapped_column(
        ForeignKey("iam.position_definitions.id", ondelete="RESTRICT"), nullable=False
    )
    organisational_unit_id: Mapped[UUID | None] = mapped_column(
        ForeignKey("tenant.organisational_units.id", ondelete="RESTRICT")
    )
    assigned_by_user_id: Mapped[UUID] = mapped_column(
        ForeignKey("iam.users.id", ondelete="RESTRICT"), nullable=False
    )
    is_primary: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    valid_from: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    valid_until: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    ended_reason: Mapped[str | None] = mapped_column(Text)


class UserInvitation(Base, UUIDPrimaryKeyMixin, TenantOwnedMixin, TimestampMixin):
    __tablename__ = "user_invitations"
    __table_args__ = (
        Index("ix_invitation_lookup", "tenant_id", "email_normalized", "status"),
        UniqueConstraint("token_hash"),
        {"schema": "iam"},
    )

    email: Mapped[str] = mapped_column(String(320), nullable=False)
    email_normalized: Mapped[str] = mapped_column(String(320), nullable=False)
    invited_by_user_id: Mapped[UUID] = mapped_column(
        ForeignKey("iam.users.id", ondelete="RESTRICT"), nullable=False
    )
    token_hash: Mapped[str] = mapped_column(String(64), nullable=False)
    status: Mapped[str] = mapped_column(
        String(30), default=InvitationStatus.PENDING.value, nullable=False
    )
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    accepted_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    revoked_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    institutional_identifier: Mapped[str | None] = mapped_column(String(100))
    position_title: Mapped[str | None] = mapped_column(String(180))
    invitation_message: Mapped[str | None] = mapped_column(Text)
    metadata_payload: Mapped[dict] = mapped_column("metadata", JSONB, default=dict, nullable=False)


class InvitationRoleGrant(Base, UUIDPrimaryKeyMixin, TenantOwnedMixin, TimestampMixin):
    __tablename__ = "invitation_role_grants"
    __table_args__ = (
        Index("ix_invitation_role_grant", "tenant_id", "invitation_id"),
        {"schema": "iam"},
    )

    invitation_id: Mapped[UUID] = mapped_column(
        ForeignKey("iam.user_invitations.id", ondelete="CASCADE"), nullable=False
    )
    role_id: Mapped[UUID] = mapped_column(
        ForeignKey("iam.roles.id", ondelete="RESTRICT"), nullable=False
    )
    scope_type: Mapped[str] = mapped_column(String(60), nullable=False)
    scope_id: Mapped[UUID | None] = mapped_column(Uuid(as_uuid=True))
    include_descendants: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    constraints: Mapped[dict] = mapped_column(JSONB, default=dict, nullable=False)


class AuthenticationSession(Base, UUIDPrimaryKeyMixin, TenantOwnedMixin, TimestampMixin):
    __tablename__ = "authentication_sessions"
    __table_args__ = (
        UniqueConstraint("refresh_token_hash"),
        Index("ix_auth_session_active", "tenant_id", "user_id", "status", "expires_at"),
        {"schema": "iam"},
    )

    user_id: Mapped[UUID] = mapped_column(
        ForeignKey("iam.users.id", ondelete="CASCADE"), nullable=False
    )
    membership_id: Mapped[UUID] = mapped_column(
        ForeignKey("iam.memberships.id", ondelete="CASCADE"), nullable=False
    )
    role_assignment_id: Mapped[UUID] = mapped_column(
        ForeignKey("iam.role_assignments.id", ondelete="RESTRICT"), nullable=False
    )
    refresh_token_hash: Mapped[str] = mapped_column(String(64), nullable=False)
    status: Mapped[str] = mapped_column(
        String(30), default=AuthSessionStatus.ACTIVE.value, nullable=False
    )
    issued_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    last_seen_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    revoked_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    revoked_reason: Mapped[str | None] = mapped_column(Text)
    rotated_from_session_id: Mapped[UUID | None] = mapped_column(
        ForeignKey("iam.authentication_sessions.id", ondelete="SET NULL")
    )
    device_label: Mapped[str | None] = mapped_column(String(180))
    user_agent_hash: Mapped[str | None] = mapped_column(String(64))
    source_ip_hash: Mapped[str | None] = mapped_column(String(64))

class InstitutionalAccessRequest(Base, UUIDPrimaryKeyMixin, TenantOwnedMixin, TimestampMixin):
    """A non-privileged request for institutional access.

    Submission never creates a user, membership, or role assignment. An
    Institution Administrator must review the request and use the existing
    invitation workflow to grant an approved role and scope.
    """

    __tablename__ = "institutional_access_requests"
    __table_args__ = (
        Index("ix_access_request_status", "tenant_id", "status", "created_at"),
        Index("ix_access_request_email", "tenant_id", "email_normalized"),
        {"schema": "iam"},
    )

    email: Mapped[str] = mapped_column(String(320), nullable=False)
    email_normalized: Mapped[str] = mapped_column(String(320), nullable=False)
    given_name: Mapped[str] = mapped_column(String(120), nullable=False)
    family_name: Mapped[str] = mapped_column(String(120), nullable=False)
    position_title: Mapped[str | None] = mapped_column(String(180))
    requested_role_code: Mapped[str | None] = mapped_column(String(80))
    request_message: Mapped[str | None] = mapped_column(Text)
    status: Mapped[str] = mapped_column(String(30), default="pending", nullable=False)
    reviewed_by_user_id: Mapped[UUID | None] = mapped_column(ForeignKey("iam.users.id"))
    reviewed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    decision_reason: Mapped[str | None] = mapped_column(Text)
    invitation_id: Mapped[UUID | None] = mapped_column(
        ForeignKey("iam.user_invitations.id", ondelete="SET NULL")
    )
    metadata_payload: Mapped[dict] = mapped_column("metadata", JSONB, default=dict, nullable=False)
