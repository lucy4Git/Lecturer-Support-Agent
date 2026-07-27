import json
from pathlib import Path


def test_hod_and_institution_admin_are_independent() -> None:
    path = Path("services/database/seeds/role_permissions.json")
    data = json.loads(path.read_text(encoding="utf-8"))
    roles = {item["code"]: set(item["permissions"]) for item in data["roles"]}
    assert "academic.assign_lecturer" in roles["head_of_department"]
    assert "academic.assign_lecturer" not in roles["institution_administrator"]
    assert "users.manage" in roles["institution_administrator"]
    assert "users.manage" not in roles["head_of_department"]


def test_authorised_teaching_roles_receive_contextual_bulk_upload() -> None:
    path = Path("services/database/seeds/role_permissions.json")
    data = json.loads(path.read_text(encoding="utf-8"))
    roles = {item["code"]: set(item["permissions"]) for item in data["roles"]}
    expected = {
        "institution_administrator", "head_of_department", "lecturer",
        "module_coordinator", "programme_coordinator", "internal_moderator",
        "external_moderator", "external_reviewer",
    }
    assert all("content.bulk_upload" in roles[code] for code in expected)
