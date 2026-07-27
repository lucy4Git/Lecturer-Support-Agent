from datetime import datetime, timezone
from uuid import UUID

import pytest

from services.api.app.core.security import (
    PasswordManager,
    TokenService,
    build_invitation_token,
    parse_invitation_tenant,
)
from services.api.app.core.settings import Settings

TENANT = UUID("11111111-1111-1111-1111-111111111111")
USER = UUID("22222222-2222-2222-2222-222222222222")
MEMBERSHIP = UUID("33333333-3333-3333-3333-333333333333")
ROLE_ASSIGNMENT = UUID("44444444-4444-4444-4444-444444444444")
SESSION = UUID("55555555-5555-5555-5555-555555555555")


def test_argon2_passwords_are_not_recoverable_and_verify() -> None:
    manager = PasswordManager(Settings(password_min_length=12))
    password = "SecureDemo!2026"
    password_hash = manager.hash(password)
    assert password not in password_hash
    assert password_hash.startswith("$argon2")
    assert manager.verify(password, password_hash)
    assert not manager.verify("wrong password", password_hash)


def test_password_policy_rejects_weak_passwords() -> None:
    manager = PasswordManager(Settings(password_min_length=12))
    with pytest.raises(ValueError):
        manager.hash("short")
    with pytest.raises(ValueError):
        manager.hash("alllowercasepassword")


def test_access_token_preserves_selected_role_context() -> None:
    settings = Settings(
        jwt_algorithm="HS256",
        jwt_secret_key="test-signing-secret-that-is-long-enough",
        access_token_minutes=15,
    )
    service = TokenService(settings)
    token, expires_at = service.create_access_token(
        user_id=USER,
        tenant_id=TENANT,
        membership_id=MEMBERSHIP,
        role_assignment_id=ROLE_ASSIGNMENT,
        role_code="head_of_department",
        session_id=SESSION,
        now=datetime(2026, 7, 24, 10, 0, tzinfo=timezone.utc),
    )
    # Decode with a current timestamp would see this fixture as expired. Use a
    # current token for the round trip and separately assert the deterministic expiry.
    assert expires_at.isoformat() == "2026-07-24T10:15:00+00:00"
    token, _ = service.create_access_token(
        user_id=USER,
        tenant_id=TENANT,
        membership_id=MEMBERSHIP,
        role_assignment_id=ROLE_ASSIGNMENT,
        role_code="head_of_department",
        session_id=SESSION,
    )
    claims = service.decode_access_token(token)
    assert claims.tenant_id == TENANT
    assert claims.subject == USER
    assert claims.membership_id == MEMBERSHIP
    assert claims.role_assignment_id == ROLE_ASSIGNMENT
    assert claims.role_code == "head_of_department"
    assert claims.session_id == SESSION


def test_opaque_refresh_and_invitation_tokens_expose_no_secret_metadata() -> None:
    service = TokenService(Settings())
    refresh = service.build_refresh_token(tenant_id=TENANT, session_id=SESSION)
    assert service.parse_refresh_token(refresh) == (TENANT, SESSION)
    assert service.hash_opaque_token(refresh) not in refresh

    invitation = build_invitation_token(TENANT)
    assert parse_invitation_tenant(invitation) == TENANT
    assert len(invitation.split(".", 1)[1]) > 40
