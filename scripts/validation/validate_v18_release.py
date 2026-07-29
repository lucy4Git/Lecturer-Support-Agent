#!/usr/bin/env python3
"""Infrastructure-independent cumulative validation for Lecturer Support Agent v1.8."""
from __future__ import annotations

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
    "services/database/models/reviews.py",
    "services/database/migrations/versions/20260725_0005_v18_moderation_external_review.py",
    "services/api/app/services/moderation_review.py",
    "services/api/app/routes/reviews.py",
    "services/api/app/schemas/reviews.py",
    "tests/unit/test_v18_moderation_review.py",
    "docs/implementation/PHASE_7_V1.8_IMPLEMENTATION_REPORT.md",
    "docs/api/V1.8_MODERATION_REVIEW_API.md",
    "docs/security/V1.8_EXTERNAL_REVIEW_ACCESS.md",
    "docs/ux/V1.8_INLINE_REVIEW_WORKFLOW.md",
    "docs/requirements/V1.8_ACCEPTANCE_CRITERIA.md",
    "docs/operations/V1.8_OWNER_MACHINE_VALIDATION.md",
    "docs/architecture/adr/ADR-012-assignment-specific-review-and-sealed-packs.md",
    "docs/architecture/uml/v1.8/README.md",
    "docs/testing/V1.8_STATIC_VALIDATION_EVIDENCE.md",
    "docs/testing/V1.8_RELEASE_VALIDATION_REPORT.md",
    "docs/testing/V1.8_RELEASE_CHECKSUMS.sha256",
    "services/moderation-review/README.md",
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
    if tables < 88:
        fail(f"Expected at least 88 SQLAlchemy tables, found {tables}")
    paths = set(_openapi_paths.keys())
    expected = {
        "/api/v1/reviews/cycles",
        "/api/v1/reviews/tasks",
        "/api/v1/reviews/tasks/{task_id}/submit",
        "/api/v1/reviews/cycles/{cycle_id}/decision",
        "/api/v1/reviews/cycles/{cycle_id}/resubmit",
        "/api/v1/reviews/dashboard/departments/{organisational_unit_id}",
        "/api/v1/external-access/grants/{grant_id}/revoke",
    }
    missing = expected - paths
    if missing:
        fail(f"Missing v1.8 API paths: {sorted(missing)}")
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


def contracts() -> None:
    models = (ROOT / "services/database/models/reviews.py").read_text(encoding="utf-8")
    for name in (
        "ReviewCycle", "ReviewPack", "ReviewPackItem", "ReviewFinding",
        "ReviewFindingResponse", "ReviewSubmission", "ReviewDecision", "ReviewCorrectionRound",
    ):
        if f"class {name}" not in models:
            fail(f"Missing review model {name}")
    service = (ROOT / "services/api/app/services/moderation_review.py").read_text(encoding="utf-8")
    for token in (
        "assignment_specific_access", "manifest_sha256", "ExternalReviewScope",
        "review_decisions.record", "blocking_without_response", "resubmit_correction",
    ):
        if token not in service:
            fail(f"Moderation service missing contract token: {token}")
    catalogue = json.loads((ROOT / "services/database/seeds/role_permissions.json").read_text())
    roles = {item["code"]: set(item["permissions"]) for item in catalogue["roles"]}
    if "review_decisions.record" in roles["institution_administrator"]:
        fail("Institution Administrator must not inherit academic review-decision authority")
    if "review_decisions.record" not in roles["head_of_department"]:
        fail("Head of Department review-decision authority missing")
    for role in ("internal_moderator", "external_moderator", "external_reviewer"):
        if "review_tasks.perform" not in roles[role]:
            fail(f"{role} assigned-task review permission missing")
    workspace = (ROOT / "apps/web/src/components/workspace-shell.tsx").read_text(encoding="utf-8")
    for token in ("Review tasks", "reviews/tasks", "Create review cycle", "review-workflow-panel"):
        if token not in workspace:
            fail(f"Unified work area missing v1.8 token: {token}")
    if "separate moderation portal" in workspace.lower():
        fail("A separate moderation portal was introduced")


def plantuml() -> int:
    count = 0
    for path in ROOT.joinpath("docs/architecture/uml").rglob("*.plantuml"):
        text = path.read_text(encoding="utf-8")
        if text.count("@startuml") != 1 or text.count("@enduml") != 1:
            fail(f"Invalid PlantUML markers: {path.relative_to(ROOT)}")
        else:
            count += 1
    return count


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
                fail(f"Forbidden secret file: {relative}")
        if any(part in forbidden_parts for part in relative.parts):
            continue
        if path.is_file() and path.suffix.lower() in suffixes:
            text = path.read_text(encoding="utf-8", errors="ignore")
            for pattern in patterns:
                if pattern.search(text):
                    fail(f"Potential provider credential in {relative}")


def cleanup() -> None:
    for path in list(ROOT.rglob("__pycache__")) + [ROOT / ".pytest_cache"]:
        if path.exists():
            shutil.rmtree(path, ignore_errors=True)


def main() -> int:
    required_files()
    tables, routes, tests = compile_and_test()
    contracts()
    uml = plantuml()
    cleanup()
    hygiene()
    print("Lecturer Support Agent v1.8 release validation")
    print(f"- Required files: {len(REQUIRED)}")
    print(f"- SQLAlchemy tables: {tables}")
    print(f"- FastAPI routes: {routes}")
    print(f"- Unit tests passed: {tests}")
    print(f"- PlantUML sources: {uml}")
    if ERRORS:
        print("FAILED")
        for error in ERRORS:
            print(f"  - {error}")
        return 1
    print("PASSED")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
