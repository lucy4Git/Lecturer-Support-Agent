#!/usr/bin/env python3
"""Validate the Data Foundation and Model Readiness Pack.

The validator is deliberately offline and deterministic. It checks JSON Schema
syntax, validates included safe examples, validates the acquisition register,
performs structural PlantUML source checks, verifies required pack files, and
checks relative Markdown links. It never reads production data or calls an AI
provider.
"""
from __future__ import annotations

import csv
import json
import pathlib
import re
import sys

try:
    from jsonschema import Draft202012Validator, FormatChecker
except ImportError as exc:  # pragma: no cover
    raise SystemExit("Install validation dependency: pip install jsonschema") from exc

ROOT = pathlib.Path(__file__).resolve().parents[2]
SCHEMA_DIR = ROOT / "data" / "schemas"
UML_DIR = ROOT / "docs" / "architecture" / "uml" / "data-foundation"
DATA_DOC_DIR = ROOT / "docs" / "data"

INSTANCE_MAP = {
    ROOT / "data" / "manifests" / "example_dataset_manifest.json": SCHEMA_DIR / "dataset_manifest.schema.json",
    ROOT / "data" / "manifests" / "example_bulk_upload_manifest.json": SCHEMA_DIR / "bulk_upload_manifest.schema.json",
    ROOT / "data" / "evaluation" / "example_evaluation_case.json": SCHEMA_DIR / "evaluation_case.schema.json",
}

REQUIRED_DOCS = {
    "README.md",
    "DATA_STRATEGY.md",
    "DATA_REQUIREMENTS_CATALOGUE.md",
    "DATASET_ACQUISITION_PLAN.md",
    "MODEL_ADAPTATION_STRATEGY.md",
    "DATABASE_ARCHITECTURE.md",
    "DATA_GOVERNANCE.md",
    "DATA_CLASSIFICATION_POLICY.md",
    "DATA_LICENSING_AND_COPYRIGHT.md",
    "DATA_PRIVACY_AND_RETENTION.md",
    "INSTITUTIONAL_DATA_ONBOARDING.md",
    "BULK_UPLOAD_SCENARIOS.md",
    "DOCUMENT_VERSIONING_STANDARD.md",
    "SOURCE_VERIFICATION_DATA_MODEL.md",
    "EVALUATION_DATASET_SPECIFICATION.md",
    "AI_SAFETY_AND_RED_TEAM_DATASET.md",
    "DATA_TRACEABILITY_MATRIX.md",
    "DATA_SOURCE_REGISTER.md",
    "DATA_FOUNDATION_VALIDATION_REPORT.md",
}

REQUIRED_SCHEMAS = {
    "dataset_manifest.schema.json",
    "document_metadata.schema.json",
    "document_version.schema.json",
    "source_record.schema.json",
    "citation_record.schema.json",
    "evaluation_case.schema.json",
    "bulk_upload_manifest.schema.json",
    "institutional_structure.schema.json",
}

REQUIRED_UML = {
    "data_architecture.plantuml",
    "data_ingestion_sequence.plantuml",
    "bulk_upload_sequence.plantuml",
    "document_versioning_state.plantuml",
    "source_verification_sequence.plantuml",
    "evaluation_data_flow.plantuml",
}

MD_LINK_RE = re.compile(r"\[[^\]]*\]\(([^)]+)\)")


def load_json(path: pathlib.Path):
    return json.loads(path.read_text(encoding="utf-8"))


def validate_required_files(errors: list[str]) -> int:
    expected = ({DATA_DOC_DIR / x for x in REQUIRED_DOCS}
                | {SCHEMA_DIR / x for x in REQUIRED_SCHEMAS}
                | {UML_DIR / x for x in REQUIRED_UML})
    count = 0
    for path in sorted(expected):
        if not path.exists():
            errors.append(f"Required file missing: {path.relative_to(ROOT)}")
        elif path.stat().st_size == 0:
            errors.append(f"Required file empty: {path.relative_to(ROOT)}")
        else:
            count += 1
    return count


def validate_schemas(errors: list[str]) -> int:
    checked = 0
    for path in sorted(SCHEMA_DIR.glob("*.schema.json")):
        try:
            Draft202012Validator.check_schema(load_json(path))
            checked += 1
        except Exception as exc:
            errors.append(f"Schema invalid: {path.relative_to(ROOT)} — {exc}")
    return checked


def validate_instances(errors: list[str]) -> int:
    checked = 0
    checker = FormatChecker()
    for instance_path, schema_path in INSTANCE_MAP.items():
        try:
            instance = load_json(instance_path)
            schema = load_json(schema_path)
            problems = sorted(
                Draft202012Validator(schema, format_checker=checker).iter_errors(instance),
                key=lambda e: list(e.path),
            )
            if problems:
                for problem in problems:
                    loc = "/".join(str(x) for x in problem.path) or "<root>"
                    errors.append(
                        f"Instance invalid: {instance_path.relative_to(ROOT)} at {loc} — {problem.message}"
                    )
            else:
                checked += 1
        except Exception as exc:
            errors.append(f"Instance validation failed: {instance_path.relative_to(ROOT)} — {exc}")
    return checked


def validate_acquisition_register(errors: list[str]) -> int:
    path = ROOT / "data" / "manifests" / "dataset_acquisition_register.csv"
    required_columns = {
        "source_id", "source_name", "data_category", "official_reference",
        "rights_summary", "status", "intended_use", "decision_or_constraint", "verified_on",
    }
    if not path.exists():
        errors.append(f"Acquisition register missing: {path.relative_to(ROOT)}")
        return 0
    with path.open(encoding="utf-8", newline="") as handle:
        reader = csv.DictReader(handle)
        columns = set(reader.fieldnames or [])
        if columns != required_columns:
            errors.append(
                f"Acquisition register columns differ: expected {sorted(required_columns)}, got {sorted(columns)}"
            )
        rows = list(reader)
    ids = [row.get("source_id", "") for row in rows]
    if len(ids) != len(set(ids)):
        errors.append("Acquisition register contains duplicate source_id values")
    for index, row in enumerate(rows, start=2):
        if not all(row.get(name, "").strip() for name in required_columns):
            errors.append(f"Acquisition register row {index} has an empty required field")
    return len(rows)


def validate_uml(errors: list[str]) -> int:
    checked = 0
    for path in sorted(UML_DIR.glob("*.plantuml")):
        text = path.read_text(encoding="utf-8")
        rel = path.relative_to(ROOT)
        if text.count("@startuml") != 1 or text.count("@enduml") != 1:
            errors.append(f"PlantUML markers invalid: {rel}")
            continue
        if text.find("@startuml") > text.find("@enduml"):
            errors.append(f"PlantUML marker order invalid: {rel}")
            continue
        if text.count("{") != text.count("}"):
            errors.append(f"PlantUML brace balance invalid: {rel}")
            continue
        if text.count('"') % 2:
            errors.append(f"PlantUML quote balance invalid: {rel}")
            continue
        if "title " not in text:
            errors.append(f"PlantUML title missing: {rel}")
            continue
        checked += 1
    return checked


def resolve_md_target(source: pathlib.Path, raw_target: str) -> pathlib.Path | None:
    target = raw_target.strip().split("#", 1)[0].strip()
    if not target or target.startswith(("http://", "https://", "mailto:", "contract://", "project://")):
        return None
    return (source.parent / target).resolve()


def validate_markdown_links(errors: list[str]) -> int:
    checked = 0
    docs = sorted(DATA_DOC_DIR.glob("*.md")) + [ROOT / "docs" / "INDEX.md", ROOT / "data" / "README.md"]
    for path in docs:
        if not path.exists():
            errors.append(f"Missing Markdown document: {path.relative_to(ROOT)}")
            continue
        text = path.read_text(encoding="utf-8")
        for raw in MD_LINK_RE.findall(text):
            target = resolve_md_target(path, raw)
            if target is None:
                continue
            checked += 1
            if not target.exists():
                errors.append(f"Broken relative link: {path.relative_to(ROOT)} -> {raw}")
    return checked


def main() -> int:
    errors: list[str] = []
    required_count = validate_required_files(errors)
    schema_count = validate_schemas(errors)
    instance_count = validate_instances(errors)
    source_count = validate_acquisition_register(errors)
    uml_count = validate_uml(errors)
    link_count = validate_markdown_links(errors)

    print("Data Foundation validation summary")
    print(f"- Required pack files present and non-empty: {required_count}")
    print(f"- JSON Schemas valid: {schema_count}")
    print(f"- Sample instances valid: {instance_count}")
    print(f"- Acquisition-register entries validated: {source_count}")
    print(f"- PlantUML sources structurally valid: {uml_count}")
    print(f"- Relative Markdown links checked: {link_count}")

    if errors:
        print(f"- Errors: {len(errors)}")
        for error in errors:
            print(f"ERROR: {error}")
        return 1

    print("- Result: PASS")
    return 0


if __name__ == "__main__":
    sys.exit(main())
