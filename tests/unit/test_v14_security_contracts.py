import json
from pathlib import Path


def test_app_role_cannot_read_password_credentials() -> None:
    policy = Path("services/database/policies/row_level_security.sql").read_text(
        encoding="utf-8"
    )
    assert "iam.password_credentials FROM lsa_app" in policy
    assert "TO lsa_app, lsa_auth" in policy


def test_position_management_remains_institution_admin_only() -> None:
    data = json.loads(
        Path("services/database/seeds/role_permissions.json").read_text(encoding="utf-8")
    )
    roles = {item["code"]: set(item["permissions"]) for item in data["roles"]}
    assert "positions.manage" in roles["institution_administrator"]
    assert "positions.manage" not in roles["head_of_department"]


def test_selected_role_is_enforced_in_authorization_query() -> None:
    source = Path("services/api/app/services/authorization.py").read_text(encoding="utf-8")
    assert "RoleAssignment.id == self.context.role_assignment_id" in source
    assert "Role.code == self.context.role_code" in source


def test_logout_is_public_for_refresh_session_revocation() -> None:
    middleware = Path("services/api/app/core/middleware.py").read_text(encoding="utf-8")
    assert '"/api/v1/auth/logout"' in middleware


def test_authentication_role_can_create_invited_users_but_app_role_cannot() -> None:
    migration = Path(
        "services/database/migrations/versions/20260724_0002_v14_identity_administration.py"
    ).read_text(encoding="utf-8")
    policy = Path("services/database/policies/row_level_security.sql").read_text(encoding="utf-8")
    assert "GRANT SELECT, INSERT, UPDATE ON iam.users TO lsa_auth" in migration
    assert "REVOKE ALL ON tenant.institutions, iam.users, iam.password_credentials FROM lsa_app" in policy


def test_every_authenticated_request_validates_backing_session() -> None:
    database = Path("services/api/app/core/database.py").read_text(encoding="utf-8")
    assert "async def validate_active_access_session" in database
    assert 'AuthenticationSession.status == "active"' in database
    assert "await validate_active_access_session(session)" in database
