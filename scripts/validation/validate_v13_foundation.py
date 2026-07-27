#!/usr/bin/env python3
from __future__ import annotations

import compileall
import json
import pathlib
import re
import sys

import yaml
from jsonschema import Draft202012Validator, FormatChecker
from sqlalchemy import create_mock_engine

ROOT = pathlib.Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))

REQUIRED = [
    "pyproject.toml",
    "alembic.ini",
    "compose.yaml",
    "services/database/migrations/versions/20260724_0001_v13_foundation.py",
    "services/database/policies/row_level_security.sql",
    "services/database/seeds/role_permissions.json",
    "services/database/seeds/seed_foundation.py",
    "services/api/app/main.py",
    "services/api/app/services/document_versioning.py",
    "services/api/app/services/authorization.py",
    "services/api/app/integrations/object_storage.py",
    "services/api/app/integrations/qdrant.py",
    "scripts/security/New-SafeProjectArchive.ps1",
    "docs/implementation/PHASE_2_V1.3_IMPLEMENTATION_REPORT.md",
    "docs/data/PHYSICAL_DATABASE_SCHEMA_V1.3.md",
    "docs/security/POSTGRESQL_RLS_IMPLEMENTATION.md",
    "docs/operations/V1.3_LOCAL_DATABASE_SETUP.md",
    "docs/architecture/adr/ADR-007-polyglot-data-foundation.md",
]

ERRORS: list[str] = []


def check_required() -> None:
    for rel in REQUIRED:
        path = ROOT / rel
        if not path.exists() or path.stat().st_size == 0:
            ERRORS.append(f"Missing or empty required file: {rel}")


def check_python() -> tuple[int, int]:
    if not compileall.compile_dir(ROOT / "services", quiet=1):
        ERRORS.append("Python compilation failed under services/")
    if not compileall.compile_dir(ROOT / "scripts", quiet=1):
        ERRORS.append("Python compilation failed under scripts/")
    from services.database.models import Base

    table_count = len(Base.metadata.tables)
    if table_count < 53:
        ERRORS.append(f"Expected at least the 53-table v1.3 baseline, found {table_count}")

    global_tables = {
        "tenant.institutions", "iam.users", "iam.roles", "iam.permissions",
        "iam.role_permissions", "iam.password_credentials"
    }
    for key, table in Base.metadata.tables.items():
        if key in global_tables:
            continue
        if table.schema in {
            "tenant", "iam", "academic", "ingestion", "content", "conversation",
            "ai", "source", "review", "audit", "privacy",
        }:
            if "tenant_id" not in table.c:
                ERRORS.append(f"Tenant-owned table lacks tenant_id: {key}")
                continue
            foreign_targets = {str(fk.target_fullname) for fk in table.c.tenant_id.foreign_keys}
            if "tenant.institutions.id" not in foreign_targets:
                ERRORS.append(f"tenant_id lacks institution FK: {key}")

    statements: list[str] = []
    engine = create_mock_engine(
        "postgresql+psycopg://",
        lambda sql, *args, **kwargs: statements.append(str(sql.compile(dialect=engine.dialect))),
    )
    Base.metadata.create_all(engine)
    if len(statements) < 130:
        ERRORS.append(f"Unexpectedly small PostgreSQL DDL output: {len(statements)}")
    return table_count, len(statements)


def check_json() -> int:
    checker = FormatChecker()
    schema_count = 0
    for path in sorted((ROOT / "data/schemas").glob("*.schema.json")):
        try:
            schema = json.loads(path.read_text(encoding="utf-8"))
            Draft202012Validator.check_schema(schema)
            schema_count += 1
        except Exception as exc:
            ERRORS.append(f"Invalid JSON Schema {path.relative_to(ROOT)}: {exc}")

    mapping = {
        "data/manifests/example_dataset_manifest.json": "data/schemas/dataset_manifest.schema.json",
        "data/manifests/example_bulk_upload_manifest.json": "data/schemas/bulk_upload_manifest.schema.json",
        "data/evaluation/example_evaluation_case.json": "data/schemas/evaluation_case.schema.json",
        "data/manifests/example_acquisition_request.json": "data/schemas/acquisition_request.schema.json",
    }
    for instance_rel, schema_rel in mapping.items():
        instance = json.loads((ROOT / instance_rel).read_text(encoding="utf-8"))
        schema = json.loads((ROOT / schema_rel).read_text(encoding="utf-8"))
        issues = list(Draft202012Validator(schema, format_checker=checker).iter_errors(instance))
        if issues:
            ERRORS.extend(f"Invalid instance {instance_rel}: {issue.message}" for issue in issues)

    role_catalogue = json.loads(
        (ROOT / "services/database/seeds/role_permissions.json").read_text(encoding="utf-8")
    )
    roles = {item["code"]: set(item["permissions"]) for item in role_catalogue["roles"]}
    if "users.manage" in roles["head_of_department"]:
        ERRORS.append("Head of Department improperly inherits users.manage")
    if "academic.assign_lecturer" in roles["institution_administrator"]:
        ERRORS.append("Institution Administrator improperly inherits HOD lecturer assignment")
    expected_bulk = {
        "institution_administrator", "head_of_department", "lecturer", "module_coordinator",
        "programme_coordinator", "internal_moderator", "external_moderator", "external_reviewer",
    }
    for role in expected_bulk:
        if "content.bulk_upload" not in roles.get(role, set()):
            ERRORS.append(f"Contextual bulk upload missing from role catalogue: {role}")
    return schema_count


def check_yaml_and_uml() -> int:
    try:
        compose = yaml.safe_load((ROOT / "compose.yaml").read_text(encoding="utf-8"))
        required_services = {"postgres", "redis", "minio", "minio-bootstrap", "qdrant"}
        missing = required_services - set(compose.get("services", {}))
        if missing:
            ERRORS.append(f"compose.yaml missing services: {sorted(missing)}")
    except Exception as exc:
        ERRORS.append(f"compose.yaml invalid: {exc}")

    uml_count = 0
    for path in sorted((ROOT / "docs/architecture/uml").rglob("*.plantuml")):
        text = path.read_text(encoding="utf-8")
        if text.count("@startuml") != 1 or text.count("@enduml") != 1:
            ERRORS.append(f"PlantUML markers invalid: {path.relative_to(ROOT)}")
        elif text.find("@startuml") > text.find("@enduml"):
            ERRORS.append(f"PlantUML marker order invalid: {path.relative_to(ROOT)}")
        elif text.count('"') % 2:
            ERRORS.append(f"PlantUML quote balance invalid: {path.relative_to(ROOT)}")
        else:
            uml_count += 1
    return uml_count


def check_powershell_and_security() -> int:
    scripts = list((ROOT / "scripts/database").glob("*.ps1")) + list(
        (ROOT / "scripts/security").glob("*.ps1")
    )
    for path in scripts:
        text = path.read_text(encoding="utf-8")
        if "Set-StrictMode" not in text:
            ERRORS.append(f"PowerShell strict mode missing: {path.relative_to(ROOT)}")
        if text.count("{") != text.count("}"):
            ERRORS.append(f"PowerShell brace imbalance: {path.relative_to(ROOT)}")
    gitignore = (ROOT / ".gitignore").read_text(encoding="utf-8")
    for required in (".env", "secrets/", "runtime/secrets/", "data/quarantine/"):
        if required not in gitignore:
            ERRORS.append(f".gitignore missing security exclusion: {required}")
    if not (ROOT / ".env.example").exists():
        ERRORS.append("Safe .env.example is missing")
    if (ROOT / ".env").exists():
        ERRORS.append("A real .env file is present in the distributable repository")
    return len(scripts)


def main() -> int:
    check_required()
    table_count, ddl_count = check_python()
    schema_count = check_json()
    uml_count = check_yaml_and_uml()
    ps_count = check_powershell_and_security()

    print("Lecturer Support Agent v1.3 baseline validation (cumulative repository)")
    print(f"- Required files checked: {len(REQUIRED)}")
    print(f"- SQLAlchemy tables: {table_count}")
    print(f"- PostgreSQL mock DDL statements: {ddl_count}")
    print(f"- JSON Schemas: {schema_count}")
    print(f"- PlantUML sources structurally checked: {uml_count}")
    print(f"- New database/security PowerShell scripts checked: {ps_count}")
    if ERRORS:
        print(f"- Result: FAIL ({len(ERRORS)} errors)")
        for error in ERRORS:
            print(f"ERROR: {error}")
        return 1
    print("- Result: PASS")
    return 0


if __name__ == "__main__":
    sys.exit(main())
