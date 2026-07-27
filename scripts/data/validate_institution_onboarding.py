from __future__ import annotations

import argparse
import json
from pathlib import Path

from jsonschema import Draft202012Validator, FormatChecker


def semantic_checks(data: dict) -> list[str]:
    errors: list[str] = []
    units = {item["external_id"]: item for item in data["organisational_units"]}
    for unit in units.values():
        parent = unit.get("parent_external_id")
        if parent is not None and parent not in units:
            errors.append(f"Unknown organisational parent: {parent}")
        visited: set[str] = set()
        current = unit
        while current.get("parent_external_id"):
            current_id = current["external_id"]
            if current_id in visited:
                errors.append(f"Organisational cycle detected at {current_id}")
                break
            visited.add(current_id)
            current = units.get(current["parent_external_id"], {})
            if not current:
                break
    for collection in ("programmes", "modules"):
        for item in data[collection]:
            owner = item["owning_unit_external_id"]
            if owner not in units:
                errors.append(f"{collection[:-1]} {item['external_id']} references unknown unit {owner}")
    emails = [item["email"].lower() for item in data["users"]]
    if len(emails) != len(set(emails)):
        errors.append("Duplicate user email detected")
    return errors


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("package")
    parser.add_argument("--schema", default="data/schemas/institution_onboarding_package.schema.json")
    args = parser.parse_args()
    data = json.loads(Path(args.package).read_text(encoding="utf-8"))
    schema = json.loads(Path(args.schema).read_text(encoding="utf-8"))
    validator = Draft202012Validator(schema, format_checker=FormatChecker())
    errors = [error.message for error in validator.iter_errors(data)] + semantic_checks(data)
    if errors:
        raise SystemExit("Onboarding package validation failed:\n- " + "\n- ".join(errors))
    print("Institution onboarding package validation passed.")


if __name__ == "__main__":
    main()
