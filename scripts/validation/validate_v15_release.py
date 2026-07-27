#!/usr/bin/env python3
"""Deterministic release validation for Lecturer Support Agent v1.5.

This validator is infrastructure-independent. It verifies source contracts,
repository hygiene, API registration, provider-neutral AI modules, source
integrity controls, documentation, and unit tests. Live database, providers,
Ollama, Crossref, and browser validation remain owner-machine work.
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
    "services/api/app/ai/contracts.py",
    "services/api/app/ai/task_classifier.py",
    "services/api/app/ai/prompt_builder.py",
    "services/api/app/ai/integrity.py",
    "services/api/app/ai/source_discovery.py",
    "services/api/app/ai/router.py",
    "services/api/app/ai/providers/openai.py",
    "services/api/app/ai/providers/anthropic.py",
    "services/api/app/ai/providers/gemini.py",
    "services/api/app/ai/providers/deepseek.py",
    "services/api/app/ai/providers/ollama.py",
    "services/api/app/services/conversation_engine.py",
    "services/api/app/routes/conversations.py",
    "services/api/app/schemas/conversations.py",
    "apps/web/src/components/workspace-shell.tsx",
    "tests/unit/test_v15_ai_conversation.py",
    "docs/implementation/PHASE_4_V1.5_IMPLEMENTATION_REPORT.md",
    "docs/api/V1.5_UNIFIED_AI_CONVERSATION_API.md",
    "docs/ai/CITATION_INTEGRITY_GUARD_V1.5.md",
    "docs/operations/V1.5_OWNER_MACHINE_VALIDATION.md",
    "docs/architecture/adr/ADR-009-unified-conversation-and-citation-integrity.md",
    "docs/architecture/uml/v1.5/README.md",
]


def check_required() -> None:
    for relative in REQUIRED:
        path = ROOT / relative
        if not path.is_file() or path.stat().st_size == 0:
            ERRORS.append(f"Missing or empty required file: {relative}")


def check_python_and_tests() -> tuple[int, int, int]:
    for directory in ("services", "scripts", "tests"):
        if not compileall.compile_dir(ROOT / directory, quiet=1):
            ERRORS.append(f"Python compilation failed under {directory}/")

    from services.api.app.main import app
    from services.database.models import Base

    table_count = len(Base.metadata.tables)
    route_count = len(app.routes)
    paths = {route.path for route in app.routes}
    required_paths = {
        "/api/v1/conversations",
        "/api/v1/conversations/providers",
        "/api/v1/conversations/{conversation_id}",
        "/api/v1/conversations/{conversation_id}/messages",
    }
    missing = required_paths - paths
    if missing:
        ERRORS.append(f"Missing conversation API paths: {sorted(missing)}")
    if table_count < 59:
        ERRORS.append(f"Expected at least 59 SQLAlchemy tables, found {table_count}")
    if route_count < 39:
        ERRORS.append(f"Expected at least 39 FastAPI routes, found {route_count}")

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
    return table_count, route_count, int(passed_match.group(1)) if passed_match else 0


def check_ai_contracts() -> None:
    settings = (ROOT / "services/api/app/core/settings.py").read_text(encoding="utf-8")
    router = (ROOT / "services/api/app/ai/router.py").read_text(encoding="utf-8")
    integrity = (ROOT / "services/api/app/ai/integrity.py").read_text(encoding="utf-8")
    prompt = (ROOT / "services/api/app/ai/prompt_builder.py").read_text(encoding="utf-8")
    main = (ROOT / "services/api/app/main.py").read_text(encoding="utf-8")
    frontend = (ROOT / "apps/web/src/components/workspace-shell.tsx").read_text(encoding="utf-8")

    expectations = {
        "production disables development mock": "The development AI mock must be disabled in production" in settings,
        "restricted privacy can force Ollama": 'configured_order = ["ollama"]' in router,
        "unknown citation markers are removed": "[unverified citation removed]" in integrity,
        "unknown links are removed": "[unverified link removed]" in integrity,
        "unknown DOIs are removed": "[unverified DOI removed]" in integrity,
        "prompt forbids invented sources": "Never create a reference list entry" in prompt,
        "provider failures map to safe 503": "provider_error_handler" in main,
        "inline sources are rendered": "source-grid" in frontend and "SourceItem" in frontend,
        "no separate artifact workspace text": "inline output" in frontend.lower(),
    }
    for description, passed in expectations.items():
        if not passed:
            ERRORS.append(f"AI contract failed: {description}")


def check_json_and_uml() -> tuple[int, int]:
    json_count = 0
    for path in ROOT.rglob("*.json"):
        if any(part in {"node_modules", ".next"} for part in path.parts):
            continue
        try:
            json.loads(path.read_text(encoding="utf-8"))
            json_count += 1
        except Exception as exc:
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
    suffixes = {".md", ".txt", ".json", ".yaml", ".yml", ".toml", ".ini", ".ps1", ".py", ".js", ".jsx", ".ts", ".tsx"}
    for path in ROOT.rglob("*"):
        if not path.is_file() or path.suffix.lower() not in suffixes:
            continue
        text = path.read_text(encoding="utf-8", errors="ignore")
        for pattern in provider_patterns:
            if pattern.search(text):
                ERRORS.append(f"Potential provider credential in {path.relative_to(ROOT)}")


def cleanup() -> None:
    for directory in list(ROOT.rglob("__pycache__")) + [ROOT / ".pytest_cache"]:
        if directory.exists():
            shutil.rmtree(directory, ignore_errors=True)


def main() -> int:
    check_required()
    table_count, route_count, tests_passed = check_python_and_tests()
    check_ai_contracts()
    json_count, uml_count = check_json_and_uml()
    cleanup()
    check_repository_hygiene()

    print("Lecturer Support Agent v1.5 release validation")
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
