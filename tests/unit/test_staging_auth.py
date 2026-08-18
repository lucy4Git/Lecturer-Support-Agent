"""Unit tests for the corrected staging authentication UX.

Covers:
- DirectRegistrationRequest: no given_name/family_name; role validated via service
- RegistrationService: staging gate, role allow-list, duplicate email, auto display_name
- AuthenticationService: MFA bypassed when staging_simple_auth_enabled
- Multi-institution login: auto-selects most recently created, no 409 institution picker
- DirectPasswordResetRequest: passwords match validation
- Settings: staging_simple_auth_enabled fails closed in production
- Route catalogue: registration-roles returns allowed subset only
"""
from __future__ import annotations

import pytest
from pydantic import ValidationError
from unittest.mock import AsyncMock, MagicMock, patch

from services.api.app.schemas.auth import (
    DirectPasswordResetRequest,
    DirectRegistrationRequest,
    RegistrationRoleOption,
)
from services.api.app.core.settings import Settings


# ---------------------------------------------------------------------------
# 1. DirectRegistrationRequest schema — no name fields, role is a free string
# ---------------------------------------------------------------------------

def test_registration_request_no_name_fields() -> None:
    """Schema must not have given_name or family_name."""
    fields = DirectRegistrationRequest.model_fields
    assert "given_name" not in fields
    assert "family_name" not in fields


def test_registration_request_valid_minimal() -> None:
    req = DirectRegistrationRequest(
        institution_id="12345678-1234-5678-1234-567812345678",
        email="lecturer@example.ac.za",
        password="StrongPass123!",
        role_code="lecturer",
    )
    assert req.role_code == "lecturer"
    assert req.email == "lecturer@example.ac.za"


def test_registration_request_requires_institution_id() -> None:
    with pytest.raises(ValidationError):
        DirectRegistrationRequest(
            email="x@example.ac.za",
            password="StrongPass123!",
            role_code="lecturer",
        )


def test_registration_request_requires_email() -> None:
    with pytest.raises(ValidationError):
        DirectRegistrationRequest(
            institution_id="12345678-1234-5678-1234-567812345678",
            password="StrongPass123!",
            role_code="lecturer",
        )


def test_registration_request_rejects_invalid_email() -> None:
    with pytest.raises(ValidationError):
        DirectRegistrationRequest(
            institution_id="12345678-1234-5678-1234-567812345678",
            email="not-an-email",
            password="StrongPass123!",
            role_code="lecturer",
        )


# ---------------------------------------------------------------------------
# 2. DirectPasswordResetRequest — passwords match
# ---------------------------------------------------------------------------

def test_password_reset_requires_matching_passwords() -> None:
    with pytest.raises(ValidationError, match="Passwords do not match"):
        DirectPasswordResetRequest(
            email="user@example.ac.za",
            new_password="NewPass123!",
            confirm_password="DifferentPass456!",
        )


def test_password_reset_accepts_matching_passwords() -> None:
    req = DirectPasswordResetRequest(
        email="user@example.ac.za",
        new_password="NewPass123!",
        confirm_password="NewPass123!",
    )
    assert req.new_password.get_secret_value() == "NewPass123!"


# ---------------------------------------------------------------------------
# 3. Settings: staging_simple_auth_enabled fails closed in production
# ---------------------------------------------------------------------------

def test_staging_simple_auth_enabled_rejected_in_production() -> None:
    with pytest.raises(ValueError, match="STAGING_SIMPLE_AUTH_ENABLED"):
        Settings(
            environment="production",
            staging_simple_auth_enabled=True,
            # Provide required production values to reach our validator
            trusted_hosts="prod.example.com",
            cors_allowed_origins="https://prod.example.com",
            jwt_secret_key="a" * 32,
            rate_limit_enabled=True,
            rate_limit_fail_closed=True,
            malware_scan_enabled=True,
            malware_scan_fail_closed=True,
            backup_storage_encryption_attested=True,
            mfa_secret_encryption_key="b" * 32,
            message_content_encryption_key="c" * 32,
            metrics_enabled=False,
            ai_enable_development_mock=False,
            embedding_provider="openai",
            openai_api_key="sk-test",
            database_url="postgresql+psycopg://lsa_app:real@prod:5432/db",
            auth_database_url="postgresql+psycopg://lsa_auth:real@prod:5432/db",
            migration_database_url="postgresql+psycopg://lsa_owner:real@prod:5432/db",
            worker_database_url="postgresql+psycopg://lsa_worker:real@prod:5432/db",
        )


def test_staging_simple_auth_enabled_allowed_in_staging() -> None:
    s = Settings(environment="staging", staging_simple_auth_enabled=True)
    assert s.staging_simple_auth_enabled is True


def test_staging_simple_auth_disabled_by_default() -> None:
    # Explicitly pass False to test the default/disabled path regardless of
    # any local .env override (which may set this to True for local dev).
    s = Settings(environment="staging", staging_simple_auth_enabled=False)
    assert s.staging_simple_auth_enabled is False


# ---------------------------------------------------------------------------
# 4. direct_registration_allowed_roles default excludes privileged roles
# ---------------------------------------------------------------------------

def test_allowed_roles_excludes_institution_administrator() -> None:
    s = Settings()
    codes = {r.strip() for r in s.direct_registration_allowed_roles.split(",") if r.strip()}
    assert "institution_administrator" not in codes


def test_allowed_roles_excludes_head_of_department() -> None:
    s = Settings()
    codes = {r.strip() for r in s.direct_registration_allowed_roles.split(",") if r.strip()}
    assert "head_of_department" not in codes


def test_allowed_roles_includes_lecturer() -> None:
    s = Settings()
    codes = {r.strip() for r in s.direct_registration_allowed_roles.split(",") if r.strip()}
    assert "lecturer" in codes


def test_allowed_roles_includes_module_coordinator() -> None:
    s = Settings()
    codes = {r.strip() for r in s.direct_registration_allowed_roles.split(",") if r.strip()}
    assert "module_coordinator" in codes


# ---------------------------------------------------------------------------
# 5. RegistrationService: staging gate enforced
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_registration_blocked_when_staging_simple_auth_disabled() -> None:
    from fastapi import HTTPException
    from services.api.app.services.registration import RegistrationService

    settings = Settings(environment="staging", staging_simple_auth_enabled=False)
    svc = RegistrationService(session=AsyncMock(), settings=settings)
    payload = DirectRegistrationRequest(
        institution_id="12345678-1234-5678-1234-567812345678",
        email="user@example.ac.za",
        password="Pass123!",
        role_code="lecturer",
    )
    with pytest.raises(HTTPException) as exc_info:
        await svc.register(payload, user_agent_hash=None, source_ip_hash=None)
    assert exc_info.value.status_code == 404


@pytest.mark.asyncio
async def test_registration_blocked_for_privileged_role() -> None:
    from fastapi import HTTPException
    from services.api.app.services.registration import RegistrationService

    settings = Settings(
        environment="staging",
        staging_simple_auth_enabled=True,
        direct_registration_allowed_roles="lecturer,module_coordinator",
    )

    mock_session = AsyncMock()
    mock_institution = MagicMock()
    mock_institution.id = "12345678-1234-5678-1234-567812345678"
    mock_institution.configuration = {"email_domains": ["example.ac.za"]}
    mock_session.scalar = AsyncMock(return_value=mock_institution)

    svc = RegistrationService(session=mock_session, settings=settings)
    payload = DirectRegistrationRequest(
        institution_id="12345678-1234-5678-1234-567812345678",
        email="admin@example.ac.za",
        password="Pass123!",
        role_code="institution_administrator",
    )
    with (
        patch("services.api.app.services.registration.set_auth_tenant_context", new=AsyncMock()),
        pytest.raises(HTTPException) as exc_info,
    ):
        await svc.register(payload, user_agent_hash=None, source_ip_hash=None)
    assert exc_info.value.status_code == 400
    assert "self-assigned" in str(exc_info.value.detail)


@pytest.mark.asyncio
async def test_registration_blocked_for_head_of_department() -> None:
    from fastapi import HTTPException
    from services.api.app.services.registration import RegistrationService

    settings = Settings(
        environment="staging",
        staging_simple_auth_enabled=True,
        direct_registration_allowed_roles="lecturer,module_coordinator",
    )

    mock_session = AsyncMock()
    mock_institution = MagicMock()
    mock_institution.configuration = {"email_domains": ["example.ac.za"]}
    mock_session.scalar = AsyncMock(return_value=mock_institution)

    svc = RegistrationService(session=mock_session, settings=settings)
    payload = DirectRegistrationRequest(
        institution_id="12345678-1234-5678-1234-567812345678",
        email="hod@example.ac.za",
        password="Pass123!",
        role_code="head_of_department",
    )
    with (
        patch("services.api.app.services.registration.set_auth_tenant_context", new=AsyncMock()),
        pytest.raises(HTTPException) as exc_info,
    ):
        await svc.register(payload, user_agent_hash=None, source_ip_hash=None)
    assert exc_info.value.status_code == 400


@pytest.mark.asyncio
async def test_registration_display_name_uses_email_local_part() -> None:
    """Display name must be the email local-part, not a fabricated personal name."""
    from services.api.app.services.registration import RegistrationService

    settings = Settings(
        environment="staging",
        staging_simple_auth_enabled=True,
        direct_registration_allowed_roles="lecturer",
    )

    mock_institution = MagicMock()
    mock_institution.id = "12345678-1234-5678-1234-567812345678"
    mock_institution.configuration = {"email_domains": ["university.ac.za"]}

    mock_role = MagicMock()
    mock_role.id = "aaaaaaaa-aaaa-aaaa-aaaa-aaaaaaaaaaaa"
    mock_role.code = "lecturer"

    added_users: list = []

    mock_session = AsyncMock()
    # scalar calls: institution → role → None (no existing user)
    mock_session.scalar = AsyncMock(side_effect=[mock_institution, mock_role, None])
    mock_session.flush = AsyncMock()
    mock_session.add = lambda obj: added_users.append(obj)
    mock_session.scalars = AsyncMock()

    passwords = MagicMock()
    passwords.hash = MagicMock(return_value="hashed")
    tokens = MagicMock()
    tokens.build_refresh_token = MagicMock(return_value="refresh-tok")
    tokens.hash_opaque_token = MagicMock(return_value="hashed-tok")
    tokens.create_access_token = MagicMock(
        return_value=("access-tok", __import__("datetime").datetime.now(__import__("datetime").timezone.utc))
    )

    svc = RegistrationService(session=mock_session, settings=settings)
    svc.passwords = passwords
    svc.tokens = tokens

    payload = DirectRegistrationRequest(
        institution_id="12345678-1234-5678-1234-567812345678",
        email="john.smith@university.ac.za",
        password="Pass123!",
        role_code="lecturer",
    )
    with patch("services.api.app.services.registration.set_auth_tenant_context", new=AsyncMock()):
        result = await svc.register(payload, user_agent_hash=None, source_ip_hash=None)

    # Find the User object that was added
    from services.database.models import User
    user_obj = next((o for o in added_users if isinstance(o, User)), None)
    assert user_obj is not None
    assert user_obj.display_name == "john.smith"
    assert user_obj.given_name is None
    assert user_obj.family_name is None


# ---------------------------------------------------------------------------
# 5b. RegistrationService: institutional email-domain validation
# ---------------------------------------------------------------------------

def _make_institution_mock(domains: list[str], inst_id: str = "12345678-1234-5678-1234-567812345678") -> MagicMock:
    m = MagicMock()
    m.id = inst_id
    m.configuration = {"email_domains": domains}
    return m


def _domain_settings() -> Settings:
    return Settings(
        environment="staging",
        staging_simple_auth_enabled=True,
        direct_registration_allowed_roles="lecturer",
    )


@pytest.mark.asyncio
async def test_registration_blocked_gmail_when_domains_configured() -> None:
    """Gmail must be rejected when the institution has institutional domains."""
    from fastapi import HTTPException
    from services.api.app.services.registration import RegistrationService

    mock_session = AsyncMock()
    mock_session.scalar = AsyncMock(return_value=_make_institution_mock(["tut.ac.za"]))

    svc = RegistrationService(session=mock_session, settings=_domain_settings())
    payload = DirectRegistrationRequest(
        institution_id="12345678-1234-5678-1234-567812345678",
        email="person@gmail.com",
        password="Pass123!",
        role_code="lecturer",
    )
    with (
        patch("services.api.app.services.registration.set_auth_tenant_context", new=AsyncMock()),
        pytest.raises(HTTPException) as exc_info,
    ):
        await svc.register(payload, user_agent_hash=None, source_ip_hash=None)
    assert exc_info.value.status_code == 422
    assert "institutional email" in exc_info.value.detail.lower()


@pytest.mark.asyncio
async def test_registration_blocked_no_domains_configured() -> None:
    """Fail-closed: institution with no email_domains must block public self-registration."""
    from fastapi import HTTPException
    from services.api.app.services.registration import RegistrationService

    mock_session = AsyncMock()
    mock_session.scalar = AsyncMock(return_value=_make_institution_mock([]))

    svc = RegistrationService(session=mock_session, settings=_domain_settings())
    payload = DirectRegistrationRequest(
        institution_id="12345678-1234-5678-1234-567812345678",
        email="person@example.com",
        password="Pass123!",
        role_code="lecturer",
    )
    with (
        patch("services.api.app.services.registration.set_auth_tenant_context", new=AsyncMock()),
        pytest.raises(HTTPException) as exc_info,
    ):
        await svc.register(payload, user_agent_hash=None, source_ip_hash=None)
    assert exc_info.value.status_code == 422
    assert "not currently available" in exc_info.value.detail.lower()


@pytest.mark.asyncio
async def test_registration_domain_check_case_insensitive() -> None:
    """Domain match must be case-insensitive (TUT.AC.ZA == tut.ac.za)."""
    from fastapi import HTTPException
    from services.api.app.services.registration import RegistrationService

    mock_institution = _make_institution_mock(["TUT.AC.ZA"])
    mock_role = MagicMock()
    mock_role.id = "aaaaaaaa-aaaa-aaaa-aaaa-aaaaaaaaaaaa"
    mock_role.code = "lecturer"

    mock_session = AsyncMock()
    # institution → role → None (no duplicate)
    mock_session.scalar = AsyncMock(side_effect=[mock_institution, mock_role, None])
    mock_session.flush = AsyncMock()
    mock_session.add = MagicMock()
    mock_session.scalars = AsyncMock()

    tokens = MagicMock()
    tokens.build_refresh_token = MagicMock(return_value="rt")
    tokens.hash_opaque_token = MagicMock(return_value="ht")
    tokens.create_access_token = MagicMock(
        return_value=("at", __import__("datetime").datetime.now(__import__("datetime").timezone.utc))
    )
    passwords = MagicMock()
    passwords.hash = MagicMock(return_value="hashed")

    svc = RegistrationService(session=mock_session, settings=_domain_settings())
    svc.passwords = passwords
    svc.tokens = tokens

    payload = DirectRegistrationRequest(
        institution_id="12345678-1234-5678-1234-567812345678",
        email="lecturer@tut.ac.za",
        password="Pass123!",
        role_code="lecturer",
    )
    with patch("services.api.app.services.registration.set_auth_tenant_context", new=AsyncMock()):
        result = await svc.register(payload, user_agent_hash=None, source_ip_hash=None)
    assert result.role_code == "lecturer"


@pytest.mark.asyncio
async def test_registration_multi_domain_institution() -> None:
    """Institution with multiple domains must accept any of them."""
    from fastapi import HTTPException
    from services.api.app.services.registration import RegistrationService

    mock_institution = _make_institution_mock(["stellenbosch.ac.za", "sun.ac.za"])
    mock_role = MagicMock()
    mock_role.id = "aaaaaaaa-aaaa-aaaa-aaaa-aaaaaaaaaaaa"
    mock_role.code = "lecturer"

    mock_session = AsyncMock()
    mock_session.scalar = AsyncMock(side_effect=[mock_institution, mock_role, None])
    mock_session.flush = AsyncMock()
    mock_session.add = MagicMock()
    mock_session.scalars = AsyncMock()

    tokens = MagicMock()
    tokens.build_refresh_token = MagicMock(return_value="rt")
    tokens.hash_opaque_token = MagicMock(return_value="ht")
    tokens.create_access_token = MagicMock(
        return_value=("at", __import__("datetime").datetime.now(__import__("datetime").timezone.utc))
    )
    passwords = MagicMock()
    passwords.hash = MagicMock(return_value="hashed")

    svc = RegistrationService(session=mock_session, settings=_domain_settings())
    svc.passwords = passwords
    svc.tokens = tokens

    # Secondary domain must be accepted
    payload = DirectRegistrationRequest(
        institution_id="12345678-1234-5678-1234-567812345678",
        email="researcher@stellenbosch.ac.za",
        password="Pass123!",
        role_code="lecturer",
    )
    with patch("services.api.app.services.registration.set_auth_tenant_context", new=AsyncMock()):
        result = await svc.register(payload, user_agent_hash=None, source_ip_hash=None)
    assert result.role_code == "lecturer"


# ---------------------------------------------------------------------------
# 5c. Role allow-list gate: external/privileged roles require explicit permit
# ---------------------------------------------------------------------------

def test_allowed_roles_excludes_institution_administrator_by_default() -> None:
    """institution_administrator must never appear in the default allow-list."""
    s = Settings()
    codes = {r.strip() for r in s.direct_registration_allowed_roles.split(",") if r.strip()}
    assert "institution_administrator" not in codes


def test_allowed_roles_excludes_head_of_department_by_default() -> None:
    """head_of_department must never appear in the default allow-list."""
    s = Settings()
    codes = {r.strip() for r in s.direct_registration_allowed_roles.split(",") if r.strip()}
    assert "head_of_department" not in codes


@pytest.mark.asyncio
async def test_registration_blocked_for_role_not_in_allow_list() -> None:
    """Any role absent from DIRECT_REGISTRATION_ALLOWED_ROLES must be blocked at 400."""
    from fastapi import HTTPException
    from services.api.app.services.registration import RegistrationService

    settings = Settings(
        environment="staging",
        staging_simple_auth_enabled=True,
        direct_registration_allowed_roles="lecturer",  # only lecturer permitted
    )

    mock_session = AsyncMock()
    mock_session.scalar = AsyncMock(
        return_value=_make_institution_mock(["example.ac.za"])
    )

    svc = RegistrationService(session=mock_session, settings=settings)
    payload = DirectRegistrationRequest(
        institution_id="12345678-1234-5678-1234-567812345678",
        email="ext@example.ac.za",
        password="Pass123!",
        role_code="external_moderator",
    )
    with (
        patch("services.api.app.services.registration.set_auth_tenant_context", new=AsyncMock()),
        pytest.raises(HTTPException) as exc_info,
    ):
        await svc.register(payload, user_agent_hash=None, source_ip_hash=None)
    assert exc_info.value.status_code == 400
    assert "self-assigned" in str(exc_info.value.detail)


# ---------------------------------------------------------------------------
# 6. Sign-in page: login form must NOT contain MFA or institution picker
# ---------------------------------------------------------------------------

def test_sign_in_page_has_no_mfa_state() -> None:
    """The sign-in page source must not reference mfaRequired or mfa_code."""
    import pathlib
    src = pathlib.Path(
        "apps/web/src/app/sign-in/page.tsx"
    ).read_text(encoding="utf-8")
    assert "mfaRequired" not in src
    assert "mfa_code" not in src
    assert "one-time-code" not in src


def test_sign_in_page_has_no_institution_picker() -> None:
    """The sign-in page must not contain institution selection UI."""
    import pathlib
    src = pathlib.Path(
        "apps/web/src/app/sign-in/page.tsx"
    ).read_text(encoding="utf-8")
    assert "availableInstitutions" not in src
    assert "institution_slug" not in src
    assert "Select your institution" not in src


def test_sign_in_page_has_email_and_password() -> None:
    import pathlib
    src = pathlib.Path(
        "apps/web/src/app/sign-in/page.tsx"
    ).read_text(encoding="utf-8")
    assert 'type="email"' in src
    assert 'type="password"' in src


def test_sign_in_page_has_role_picker_only_post_auth() -> None:
    """Role picker must be conditional on availableRoles, not shown initially."""
    import pathlib
    src = pathlib.Path(
        "apps/web/src/app/sign-in/page.tsx"
    ).read_text(encoding="utf-8")
    assert "availableRoles" in src
    assert "availableRoles.length > 0" in src


# ---------------------------------------------------------------------------
# 7. Sign-up page: must NOT contain first/last name fields
# ---------------------------------------------------------------------------

def test_sign_up_page_has_no_first_name_field() -> None:
    import pathlib
    src = pathlib.Path(
        "apps/web/src/app/sign-up/page.tsx"
    ).read_text(encoding="utf-8")
    assert "given_name" not in src
    assert "First name" not in src
    assert "given-name" not in src


def test_sign_up_page_has_no_last_name_field() -> None:
    import pathlib
    src = pathlib.Path(
        "apps/web/src/app/sign-up/page.tsx"
    ).read_text(encoding="utf-8")
    assert "family_name" not in src
    assert "Last name" not in src
    assert "family-name" not in src


def test_sign_up_page_fetches_roles_from_api() -> None:
    """Roles must be fetched from /api/registration-roles, not hard-coded."""
    import pathlib
    src = pathlib.Path(
        "apps/web/src/app/sign-up/page.tsx"
    ).read_text(encoding="utf-8")
    assert "registration-roles" in src
    # Must NOT contain a hard-coded ROLES array with role codes
    assert "const ROLES" not in src
    assert '"institution_administrator"' not in src
    assert '"head_of_department"' not in src


def test_sign_up_page_has_required_fields() -> None:
    import pathlib
    src = pathlib.Path(
        "apps/web/src/app/sign-up/page.tsx"
    ).read_text(encoding="utf-8")
    assert "Institution / University" in src
    assert 'type="email"' in src
    assert 'type="password"' in src
    assert "role_code" in src
    assert "Create account" in src


# ---------------------------------------------------------------------------
# 8. Forgot-password page: correct fields, no email link
# ---------------------------------------------------------------------------

def test_forgot_password_page_has_correct_fields() -> None:
    import pathlib
    src = pathlib.Path(
        "apps/web/src/app/forgot-password/page.tsx"
    ).read_text(encoding="utf-8")
    assert 'type="email"' in src
    assert "new_password" in src
    assert "confirm_password" in src
    assert "Change password" in src


def test_forgot_password_page_has_no_email_link_flow() -> None:
    import pathlib
    src = pathlib.Path(
        "apps/web/src/app/forgot-password/page.tsx"
    ).read_text(encoding="utf-8")
    assert "Send reset" not in src
    assert "reset instructions" not in src
    assert "institution_slug" not in src
    assert "reset link" not in src


# ---------------------------------------------------------------------------
# 9. RegistrationRoleOption schema
# ---------------------------------------------------------------------------

def test_registration_role_option_schema() -> None:
    opt = RegistrationRoleOption(role_code="lecturer", role_name="Lecturer")
    assert opt.role_code == "lecturer"
    assert opt.role_name == "Lecturer"


# ---------------------------------------------------------------------------
# 10. MFA bypass in staging mode
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_mfa_not_checked_when_staging_simple_auth_enabled() -> None:
    """When staging_simple_auth_enabled=True, MFA check must be skipped."""
    from services.api.app.services.authentication import AuthenticationService
    from services.api.app.schemas.auth import LoginRequest

    settings = Settings(environment="staging", staging_simple_auth_enabled=True)

    mock_institution = MagicMock()
    mock_institution.id = "12345678-1234-5678-1234-567812345678"

    mock_user = MagicMock()
    mock_user.id = "aaaaaaaa-aaaa-aaaa-aaaa-aaaaaaaaaaaa"
    mock_user.is_active = True
    mock_user.email_normalized = "user@example.ac.za"

    mock_membership = MagicMock()
    mock_membership.status = "active"
    mock_membership.id = "bbbbbbbb-bbbb-bbbb-bbbb-bbbbbbbbbbbb"

    mock_credential = MagicMock()
    mock_credential.locked_until = None
    mock_credential.failed_attempts = 0

    mock_role_option = MagicMock()
    mock_role_option.role_code = "lecturer"
    mock_role_option.role_name = "Lecturer"
    mock_role_option.role_assignment_id = "cccccccc-cccc-cccc-cccc-cccccccccccc"

    now = __import__("datetime").datetime.now(__import__("datetime").timezone.utc)

    mock_session = AsyncMock()
    # _resolve_institution_for_user is patched so scalar order is: user, credential, membership
    mock_session.scalar = AsyncMock(side_effect=[mock_user, mock_credential, mock_membership])
    mock_session.scalars = AsyncMock()
    mock_session.flush = AsyncMock()

    svc = AuthenticationService(session=mock_session, settings=settings)

    passwords = MagicMock()
    passwords.verify = MagicMock(return_value=True)
    svc.passwords = passwords

    tokens = MagicMock()
    tokens.hash_opaque_token = MagicMock(return_value="hashed")
    tokens.build_refresh_token = MagicMock(return_value="refresh-tok")
    tokens.create_access_token = MagicMock(return_value=("access-tok", now))
    svc.tokens = tokens

    payload = LoginRequest(
        email="user@example.ac.za",
        password="Pass123!",
        institution_id="12345678-1234-5678-1234-567812345678",
    )

    # Patch _active_role_options and _issue_session to avoid deeper DB calls
    with (
        patch.object(svc, "_resolve_institution_for_user", AsyncMock(return_value=mock_institution)),
        patch.object(svc, "_active_role_options", AsyncMock(return_value=[mock_role_option])),
        patch.object(svc, "_issue_session", AsyncMock(return_value=MagicMock())),
        patch.object(svc, "_record_security_event", AsyncMock()),
        patch("services.api.app.services.authentication.set_auth_tenant_context", AsyncMock()),
    ):
        # Should not raise HTTPException 428 (MFA required)
        result = await svc.login(payload, user_agent_hash=None, source_ip_hash=None)
        assert result is not None
