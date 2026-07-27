#!/usr/bin/env python3
"""Deterministic release validation for the cumulative Lecturer Support Agent v1.4 pack.

This validator is intentionally infrastructure-independent. It verifies source,
metadata, security contracts, documentation assets, and repository hygiene.
Owner-machine PostgreSQL, Docker, browser, and provider checks remain separate.
"""
from __future__ import annotations

import compileall
import json
import pathlib
import re
import shutil
import subprocess
import sys

ROOT = pathlib.Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))

ERRORS: list[str] = []
REQUIRED = [
    "README.md",
    "CLAUDE.md",
    "PROJECT_CONSTITUTION.md",
    "pyproject.toml",
    "compose.yaml",
    ".env.example",
    "services/api/app/core/security.py",
    "services/api/app/core/middleware.py",
    "services/api/app/services/authentication.py",
    "services/api/app/services/user_administration.py",
    "services/api/app/services/organisation.py",
    "services/api/app/services/assignments.py",
    "services/database/migrations/versions/20260724_0002_v14_identity_administration.py",
    "apps/web/package.json",
    "apps/web/src/components/workspace-shell.tsx",
    "docs/implementation/PHASE_3_V1.4_IMPLEMENTATION_REPORT.md",
    "docs/security/AUTHENTICATION_AND_SESSION_SECURITY_V1.4.md",
    "docs/operations/V1.4_OWNER_MACHINE_VALIDATION.md",
    "docs/architecture/adr/ADR-008-active-role-session-and-bff.md",
]


def check_required() -> None:
    for relative in REQUIRED:
        path = ROOT / relative
        if not path.is_file() or path.stat().st_size == 0:
            ERRORS.append(f"Missing or empty required file: {relative}")


def check_python_and_tests() -> tuple[int, int, int]:
    if not compileall.compile_dir(ROOT / "services", quiet=1):
        ERRORS.append("Python compilation failed under services/")
    if not compileall.compile_dir(ROOT / "scripts", quiet=1):
        ERRORS.append("Python compilation failed under scripts/")
    if not compileall.compile_dir(ROOT / "tests", quiet=1):
        ERRORS.append("Python compilation failed under tests/")

    from services.api.app.main import app
    from services.database.models import Base

    table_count = len(Base.metadata.tables)
    route_count = len(app.routes)
    if table_count < 59:
        ERRORS.append(f"Expected at least 59 SQLAlchemy tables, found {table_count}")
    if route_count < 33:
        ERRORS.append(f"Expected at least 33 FastAPI routes, found {route_count}")

    result = subprocess.run(
        [sys.executable, "-m", "pytest", "tests/unit", "-q"],
        cwd=ROOT,
        capture_output=True,
        text=True,
        check=False,
    )
    if result.returncode:
        ERRORS.append("Unit tests failed:\n" + result.stdout + result.stderr)
    passed_match = re.search(r"(\d+) passed", result.stdout)
    passed = int(passed_match.group(1)) if passed_match else 0
    return table_count, route_count, passed


def check_json_and_uml() -> tuple[int, int]:
    json_count = 0
    for path in ROOT.rglob("*.json"):
        if any(part in {"node_modules", ".next"} for part in path.parts):
            continue
        try:
            json.loads(path.read_text(encoding="utf-8"))
            json_count += 1
        except Exception as exc:  # pragma: no cover - release diagnostic
            ERRORS.append(f"Invalid JSON {path.relative_to(ROOT)}: {exc}")

    uml_count = 0
    for path in ROOT.joinpath("docs/architecture/uml").rglob("*.plantuml"):
        text = path.read_text(encoding="utf-8")
        if text.count("@startuml") != 1 or text.count("@enduml") != 1:
            ERRORS.append(f"Invalid PlantUML markers: {path.relative_to(ROOT)}")
        elif text.find("@startuml") > text.find("@enduml"):
            ERRORS.append(f"Invalid PlantUML marker order: {path.relative_to(ROOT)}")
        elif text.count('"') % 2:
            ERRORS.append(f"Unbalanced PlantUML quotes: {path.relative_to(ROOT)}")
        else:
            uml_count += 1
    return json_count, uml_count


def check_security_contracts() -> None:
    middleware = (ROOT / "services/api/app/core/middleware.py").read_text(encoding="utf-8")
    database = (ROOT / "services/api/app/core/database.py").read_text(encoding="utf-8")
    authorization = (ROOT / "services/api/app/services/authorization.py").read_text(
        encoding="utf-8"
    )
    migration = (
        ROOT
        / "services/database/migrations/versions/20260724_0002_v14_identity_administration.py"
    ).read_text(encoding="utf-8")
    policy = (ROOT / "services/database/policies/row_level_security.sql").read_text(
        encoding="utf-8"
    )
    roles = json.loads(
        (ROOT / "services/database/seeds/role_permissions.json").read_text(encoding="utf-8")
    )
    role_map = {item["code"]: set(item["permissions"]) for item in roles["roles"]}

    expectations = {
        "logout remains available for refresh-session revocation": '"/api/v1/auth/logout"' in middleware,
        "protected requests validate the backing session": "validate_active_access_session" in database,
        "authorisation binds to selected role assignment": "RoleAssignment.id == self.context.role_assignment_id" in authorization,
        "auth role can create invited users": "GRANT SELECT, INSERT, UPDATE ON iam.users TO lsa_auth" in migration,
        "app role cannot read global credentials": "iam.password_credentials FROM lsa_app" in policy,
        "HOD does not inherit user administration": "users.manage" not in role_map["head_of_department"],
        "institution admin does not inherit HOD lecturer assignment": "academic.assign_lecturer" not in role_map["institution_administrator"],
    }
    for description, passed in expectations.items():
        if not passed:
            ERRORS.append(f"Security contract failed: {description}")



def cleanup_generated_validation_files() -> None:
    for directory in list(ROOT.rglob("__pycache__")) + [ROOT / ".pytest_cache"]:
        if directory.exists():
            shutil.rmtree(directory, ignore_errors=True)


def check_repository_hygiene() -> None:
    forbidden_names = {".env", ".env.local", ".env.production", ".env.development"}
    forbidden_parts = {"node_modules", ".next", ".pytest_cache", "__pycache__", ".git"}
    for path in ROOT.rglob("*"):
        relative = path.relative_to(ROOT)
        if path.name in forbidden_names:
            ERRORS.append(f"Forbidden secret file in release: {relative}")
        if any(part in forbidden_parts for part in relative.parts):
            ERRORS.append(f"Generated/runtime path in release: {relative}")
            break

    provider_patterns = [
        re.compile(r"sk-ant-[A-Za-z0-9_-]{20,}"),
        re.compile(r"sk-[A-Za-z0-9_-]{20,}"),
        re.compile(r"AIza[0-9A-Za-z_-]{25,}"),
    ]
    text_suffixes = {".md", ".txt", ".json", ".yaml", ".yml", ".toml", ".ini", ".ps1", ".py", ".js", ".jsx", ".ts", ".tsx"}
    for path in ROOT.rglob("*"):
        if not path.is_file() or path.suffix.lower() not in text_suffixes:
            continue
        text = path.read_text(encoding="utf-8", errors="ignore")
        for pattern in provider_patterns:
            if pattern.search(text):
                ERRORS.append(f"Potential provider credential in {path.relative_to(ROOT)}")


def main() -> int:
    check_required()
    table_count, route_count, tests_passed = check_python_and_tests()
    json_count, uml_count = check_json_and_uml()
    check_security_contracts()
    cleanup_generated_validation_files()
    check_repository_hygiene()

    print("Lecturer Support Agent v1.4 release validation")
    print(f"- Required files: {len(REQUIRED)}")
    print(f"- SQLAlchemy tables: {table_count}")
    print(f"- FastAPI routes: {route_count}")
    print(f"- Unit tests passed: {tests_passed}")
    print(f"- JSON files parsed: {json_count}")
    print(f"- PlantUML sources structurally checked: {uml_count}")
    if ERRORS:
        print(f"- Result: FAIL ({len(ERRORS)} errors)")
        for error in ERRORS:
            print(f"ERROR: {error}")
        return 1
    print("- Result: PASS")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
