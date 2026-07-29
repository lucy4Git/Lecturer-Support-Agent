#!/usr/bin/env python3
"""Infrastructure-independent cumulative validation for Lecturer Support Agent v1.7."""
from __future__ import annotations

import ast
import compileall
import hashlib
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
    "services/database/models/production.py",
    "services/database/migrations/versions/20260725_0004_v17_teaching_outputs.py",
    "services/api/app/services/assessment_safety.py",
    "services/api/app/services/teaching_output_workflow.py",
    "services/api/app/services/module_context.py",
    "services/api/app/services/generated_outputs.py",
    "services/api/app/services/export_generation.py",
    "services/api/app/services/teaching_output_exports.py",
    "services/api/app/routes/teaching_contexts.py",
    "services/api/app/routes/teaching_outputs.py",
    "services/api/app/schemas/teaching_outputs.py",
    "tests/unit/test_v17_teaching_outputs.py",
    "packages/artifact-schemas/src/teaching_output.schema.json",
    "packages/artifact-schemas/src/lesson_plan.schema.json",
    "packages/artifact-schemas/src/assessment_package.schema.json",
    "packages/artifact-schemas/src/rubric.schema.json",
    "packages/artifact-schemas/src/marking_guide.schema.json",
    "docs/implementation/PHASE_6_V1.7_IMPLEMENTATION_REPORT.md",
    "docs/api/V1.7_TEACHING_OUTPUT_API.md",
    "docs/ai/V1.7_TEACHING_OUTPUT_PRODUCTION.md",
    "docs/security/V1.7_ASSESSMENT_SAFETY.md",
    "docs/ux/V1.7_INLINE_EDIT_VERSION_EXPORT.md",
    "docs/requirements/V1.7_ACCEPTANCE_CRITERIA.md",
    "docs/operations/V1.7_OWNER_MACHINE_VALIDATION.md",
    "docs/architecture/adr/ADR-011-inline-output-lifecycle-and-assessment-safety.md",
    "docs/architecture/uml/v1.7/README.md",
]


def fail(message: str) -> None:
    ERRORS.append(message)


def required_files() -> None:
    for relative in REQUIRED:
        path = ROOT / relative
        if not path.is_file() or path.stat().st_size == 0:
            fail(f"Missing or empty required file: {relative}")


def compile_and_test() -> tuple[int, int, int]:
    for directory in ("services", "scripts", "tests"):
        if not compileall.compile_dir(ROOT / directory, quiet=1):
            fail(f"Python compilation failed under {directory}/")
    from services.api.app.main import app
    from services.database.models import Base

    tables = len(Base.metadata.tables)
    _openapi_paths = app.openapi()["paths"]
    routes = len(_openapi_paths)
    if tables < 69:
        fail(f"Expected at least 69 SQLAlchemy tables, found {tables}")
    paths = list(_openapi_paths.keys())
    expected = {
        "/api/v1/teaching-contexts",
        "/api/v1/teaching-outputs/{output_id}",
        "/api/v1/teaching-outputs/{output_id}/versions",
        "/api/v1/teaching-outputs/{output_id}/versions/{source_version_id}/restore",
        "/api/v1/teaching-outputs/{output_id}/workflow",
        "/api/v1/teaching-outputs/{output_id}/exports",
        "/api/v1/teaching-outputs/exports/{export_id}/download",
    }
    missing = expected - set(paths)
    if missing:
        fail(f"Missing v1.7 API paths: {sorted(missing)}")
    try:
        if paths.index("/api/v1/teaching-outputs/exports/{export_id}/download") > paths.index(
            "/api/v1/teaching-outputs/{output_id}"
        ):
            fail("Static export download route must precede dynamic output route")
    except ValueError:
        pass

    result = subprocess.run(
        [sys.executable, "-m", "pytest", "tests/unit", "-q"],
        cwd=ROOT,
        capture_output=True,
        text=True,
        check=False,
    )
    if result.returncode:
        fail("Unit tests failed:\n" + result.stdout + result.stderr)
    match = re.search(r"(\d+) passed", result.stdout)
    return tables, routes, int(match.group(1)) if match else 0


def contract_checks() -> None:
    production = (ROOT / "services/database/models/production.py").read_text(encoding="utf-8")
    for model in (
        "ModuleContextSnapshot",
        "OutputLifecycle",
        "AssessmentSafetyReview",
        "OutputWorkflowAction",
        "ExportJob",
    ):
        if f"class {model}" not in production:
            fail(f"Missing v1.7 model {model}")

    migration = (ROOT / REQUIRED[1]).read_text(encoding="utf-8")
    for table in (
        "module_context_snapshots",
        "output_lifecycles",
        "assessment_safety_reviews",
        "output_workflow_actions",
        "export_jobs",
    ):
        if table not in migration:
            fail(f"Migration does not create/reference {table}")
    if "row_level_security.sql" not in migration and "ROW LEVEL SECURITY" not in migration:
        fail("Migration does not show RLS policy application")

    roles = json.loads((ROOT / "services/database/seeds/role_permissions.json").read_text())
    role_map = {item["code"]: set(item["permissions"]) for item in roles["roles"]}
    if "outputs.approve" in role_map["institution_administrator"]:
        fail("Institution Administrator must not inherit academic approval")
    if "outputs.approve" not in role_map["head_of_department"]:
        fail("Head of Department approval permission missing")
    if "outputs.review" not in role_map["external_moderator"]:
        fail("External moderator review permission missing")
    if "outputs.edit" in role_map["external_reviewer"]:
        fail("External reviewer must not have unrestricted output editing")

    workspace = (ROOT / "apps/web/src/components/workspace-shell.tsx").read_text(encoding="utf-8")
    for token in ("module_offering_id", "version-pill", "student_copy", "Restore"):
        if token not in workspace:
            fail(f"Unified work area missing v1.7 UI contract token: {token}")
    if "separate artifact workspace" in workspace.lower():
        fail("A separate artifact workspace was introduced")

    safety = (ROOT / "services/api/app/services/assessment_safety.py").read_text(encoding="utf-8")
    for phrase in ("answers_detected", "personal_data_detected", "student_copy_safe"):
        if phrase not in safety:
            fail(f"Assessment-safety contract missing {phrase}")


def json_schema_and_uml() -> tuple[int, int, int]:
    json_count = schema_count = uml_count = 0
    try:
        from jsonschema.validators import validator_for
    except Exception as exc:  # pragma: no cover
        fail(f"jsonschema is unavailable: {exc}")
        validator_for = None

    for path in ROOT.rglob("*.json"):
        if any(part in {"node_modules", ".next"} for part in path.parts):
            continue
        try:
            data = json.loads(path.read_text(encoding="utf-8"))
            json_count += 1
            if path.name.endswith(".schema.json"):
                schema_count += 1
                if validator_for:
                    validator_for(data).check_schema(data)
        except Exception as exc:
            fail(f"Invalid JSON/schema {path.relative_to(ROOT)}: {exc}")

    for path in ROOT.joinpath("docs/architecture/uml").rglob("*.plantuml"):
        text = path.read_text(encoding="utf-8")
        if text.count("@startuml") != 1 or text.count("@enduml") != 1:
            fail(f"Invalid PlantUML markers: {path.relative_to(ROOT)}")
        elif text.index("@startuml") > text.index("@enduml"):
            fail(f"Invalid PlantUML marker order: {path.relative_to(ROOT)}")
        elif text.count('"') % 2:
            fail(f"Unbalanced PlantUML quotes: {path.relative_to(ROOT)}")
        else:
            uml_count += 1
    return json_count, schema_count, uml_count


def markdown_links() -> int:
    checked = 0
    link_re = re.compile(r"\[[^\]]*\]\(([^)]+)\)")
    _skip = {"node_modules", ".next", "runtime"}
    for path in ROOT.rglob("*.md"):
        if any(part in _skip for part in path.parts):
            continue
        text = path.read_text(encoding="utf-8", errors="ignore")
        for target in link_re.findall(text):
            target = target.strip().split("#", 1)[0]
            if not target or "://" in target or target.startswith(("mailto:", "#")):
                continue
            target = target.split(" ", 1)[0].strip("<>")
            candidate = (path.parent / target).resolve()
            checked += 1
            if not candidate.exists():
                fail(f"Broken relative Markdown link in {path.relative_to(ROOT)}: {target}")
    return checked


def hygiene() -> None:
    import subprocess as _sp
    forbidden_names = {".env", ".env.local", ".env.production", ".env.development"}
    forbidden_parts = {"node_modules", ".next", ".pytest_cache", "__pycache__", ".git", "runtime"}
    patterns = [
        re.compile(r"sk-ant-[A-Za-z0-9_-]{20,}"),
        re.compile(r"sk-[A-Za-z0-9_-]{20,}"),
        re.compile(r"AIza[0-9A-Za-z_-]{25,}"),
    ]
    suffixes = {".md", ".txt", ".json", ".yaml", ".yml", ".toml", ".ini", ".ps1", ".py", ".js", ".jsx", ".ts", ".tsx"}
    for path in ROOT.rglob("*"):
        relative = path.relative_to(ROOT)
        if path.name in forbidden_names:
            # Only fail if git-tracked; git-ignored local files are owner-machine artefacts
            if _sp.run(["git", "ls-files", "--error-unmatch", str(relative)], cwd=ROOT, capture_output=True).returncode == 0:
                fail(f"Forbidden secret file in release: {relative}")
        if any(part in forbidden_parts for part in relative.parts):
            continue
        if path.is_file() and path.suffix.lower() in suffixes:
            text = path.read_text(encoding="utf-8", errors="ignore")
            for pattern in patterns:
                if pattern.search(text):
                    fail(f"Potential provider credential in {relative}")


def cleanup() -> None:
    for directory in list(ROOT.rglob("__pycache__")) + [ROOT / ".pytest_cache"]:
        if directory.exists():
            shutil.rmtree(directory, ignore_errors=True)


def main() -> int:
    required_files()
    tables, routes, tests = compile_and_test()
    contract_checks()
    json_count, schemas, uml = json_schema_and_uml()
    links = markdown_links()
    cleanup()
    hygiene()
    print("Lecturer Support Agent v1.7 release validation")
    print(f"- Required files: {len(REQUIRED)}")
    print(f"- SQLAlchemy tables: {tables}")
    print(f"- FastAPI routes: {routes}")
    print(f"- Unit tests passed: {tests}")
    print(f"- JSON files parsed: {json_count}")
    print(f"- JSON Schemas checked: {schemas}")
    print(f"- PlantUML sources structurally checked: {uml}")
    print(f"- Relative Markdown links checked: {links}")
    if ERRORS:
        print(f"- Result: FAIL ({len(ERRORS)} errors)")
        for error in ERRORS:
            print(f"ERROR: {error}")
        return 1
    print("- Result: PASS")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
