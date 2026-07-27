from __future__ import annotations

import json
from pathlib import Path

from services.api.app.services.workspace import navigation_for_role, normalise_search_query
from services.database.models import Base

ROOT = Path(__file__).resolve().parents[2]


def test_v21_registers_workspace_tables() -> None:
    tables = set(Base.metadata.tables)
    assert len(tables) >= 90
    assert "conversation.saved_outputs" in tables
    assert "governance.notifications" in tables


def test_navigation_is_unified_and_role_actions_remain_independent() -> None:
    admin = navigation_for_role("institution_administrator", unread_count=4)
    hod = navigation_for_role("head_of_department", unread_count=0)
    keys = [item["key"] for item in admin["items"]]
    assert keys[:6] == ["conversation", "search", "library", "files", "saved", "notifications"]
    assert next(item for item in admin["items"] if item["key"] == "notifications")["badge_count"] == 4
    assert "users" in admin["role_actions"]
    assert "module_assignments" not in admin["role_actions"]
    assert "module_assignments" in hod["role_actions"]
    assert "users" not in hod["role_actions"]


def test_search_query_is_normalised_and_bounded() -> None:
    assert normalise_search_query("  IoT   sensors  ") == "IoT sensors"
    for invalid in [" ", "x", "x" * 201]:
        try:
            normalise_search_query(invalid)
        except ValueError:
            pass
        else:
            raise AssertionError("Expected invalid search query to fail closed")


def test_role_catalogue_grants_personal_workspace_permissions_to_every_role() -> None:
    catalogue = json.loads((ROOT / "services/database/seeds/role_permissions.json").read_text())
    required = {"workspace.search", "saved_outputs.manage", "notifications.read"}
    assert required.issubset({item["code"] for item in catalogue["permissions"]})
    for role in catalogue["roles"]:
        assert required.issubset(set(role["permissions"])), role["code"]


def test_frontend_exposes_commercial_views_without_separate_artifact_workspace() -> None:
    shell = (ROOT / "apps/web/src/components/workspace-shell.tsx").read_text()
    panels = (ROOT / "apps/web/src/components/workspace-resource-panels.tsx").read_text()
    assert 'activeView' in shell
    for label in ["Search", "Library", "Files", "Saved outputs", "Notifications"]:
        assert label in shell or label in panels
    assert "Attach to conversation" in panels
    assert "separate artifact workspace" not in (shell + panels).lower()


def test_v21_migration_reapplies_rls_including_governance_schema() -> None:
    migration = (ROOT / "services/database/migrations/versions/20260725_0007_v21_commercial_workspace.py").read_text()
    rls = (ROOT / "services/database/policies/row_level_security.sql").read_text()
    assert "SavedOutput.__table__" in migration
    assert "Notification.__table__" in migration
    assert "row_level_security.sql" in migration
    assert "'governance'" in rls


def test_operational_services_emit_actionable_notifications() -> None:
    files = [
        ROOT / "services/api/app/services/assignments.py",
        ROOT / "services/api/app/services/external_access.py",
        ROOT / "services/api/app/services/moderation_review.py",
    ]
    combined = "\n".join(path.read_text() for path in files)
    for event in [
        "module_assignment",
        "moderation_assignment",
        "temporary_access_granted",
        "temporary_access_revoked",
        "review_task_assigned",
        "review_correction_resubmitted",
    ]:
        assert event in combined
    assert "NotificationService" in combined
