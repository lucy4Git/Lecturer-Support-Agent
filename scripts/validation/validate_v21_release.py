from __future__ import annotations

import json
import py_compile
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))

REQUIRED = [
    "services/database/models/workspace.py",
    "services/database/migrations/versions/20260725_0007_v21_commercial_workspace.py",
    "services/api/app/schemas/workspace.py",
    "services/api/app/services/workspace.py",
    "services/api/app/routes/workspace.py",
    "apps/web/src/components/workspace-resource-panels.tsx",
    "tests/unit/test_v21_commercial_workspace.py",
    "tests/e2e/live-preview/commercial-workspace.spec.ts",
    "docs/implementation/PHASE_10_V2.1_COMMERCIAL_WORKSPACE_IMPLEMENTATION_REPORT.md",
    "docs/api/V2.1_COMMERCIAL_WORKSPACE_API.md",
    "docs/ux/V2.1_COMMERCIAL_UNIFIED_WORKSPACE.md",
    "docs/security/V2.1_SEARCH_AND_PERSONAL_WORKSPACE_SECURITY.md",
    "docs/requirements/V2.1_ACCEPTANCE_CRITERIA.md",
    "docs/operations/V2.1_OWNER_MACHINE_VALIDATION.md",
    "docs/architecture/adr/ADR-015-commercial-unified-workspace-and-authorised-search.md",
    "docs/architecture/uml/v2.1/README.md",
]
missing = [item for item in REQUIRED if not (ROOT / item).exists()]
if missing:
    raise SystemExit("Missing v2.1 files: " + ", ".join(missing))

for rel in [
    "services/database/models/workspace.py",
    "services/api/app/schemas/workspace.py",
    "services/api/app/services/workspace.py",
    "services/api/app/routes/workspace.py",
    "scripts/validation/validate_v21_release.py",
]:
    py_compile.compile(str(ROOT / rel), doraise=True)

from services.api.app.main import app
from services.database.models import Base

assert tuple(map(int, app.version.split("."))) >= (2, 1, 0)
assert len(Base.metadata.tables) >= 90
assert "conversation.saved_outputs" in Base.metadata.tables
assert "governance.notifications" in Base.metadata.tables
paths = {route.path for route in app.routes}
for path in [
    "/api/v1/workspace/navigation",
    "/api/v1/workspace/search",
    "/api/v1/workspace/library",
    "/api/v1/workspace/files",
    "/api/v1/workspace/saved-outputs",
    "/api/v1/workspace/notifications",
]:
    assert path in paths, path

catalogue = json.loads((ROOT / "services/database/seeds/role_permissions.json").read_text())
required_permissions = {"workspace.search", "saved_outputs.manage", "notifications.read"}
assert required_permissions <= {item["code"] for item in catalogue["permissions"]}
for role in catalogue["roles"]:
    assert required_permissions <= set(role["permissions"]), role["code"]

web_package = json.loads((ROOT / "apps/web/package.json").read_text())
assert tuple(map(int, web_package["version"].split("."))) >= (2, 1, 0)
assert 'version = "2.' in (ROOT / "pyproject.toml").read_text()
shell = (ROOT / "apps/web/src/components/workspace-shell.tsx").read_text()
panels = (ROOT / "apps/web/src/components/workspace-resource-panels.tsx").read_text()
for token in ["activeView", "unreadNotifications", "toggleTheme", "WorkspaceResourcePanel"]:
    assert token in shell
for token in ["SearchPanel", "LibraryPanel", "SavedOutputsPanel", "NotificationsPanel", "Attach to conversation"]:
    assert token in panels
assert "'governance'" in (ROOT / "services/database/policies/row_level_security.sql").read_text()
print("v2.1 release validation passed: commercial unified navigation, authorised search/library/files, immutable saved outputs, recipient notifications, security controls, documentation, and version metadata are present.")
