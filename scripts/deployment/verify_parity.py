"""Compare local and deployed parity manifests and fail on material drift."""
from __future__ import annotations

import argparse
import json
from pathlib import Path


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("local")
    parser.add_argument("deployed")
    args = parser.parse_args()
    local = json.loads(Path(args.local).read_text(encoding="utf-8"))
    deployed = json.loads(Path(args.deployed).read_text(encoding="utf-8"))
    checks = {
        "application.version": (local["application"]["version"], deployed["application"]["version"]),
        "database.alembic_revision": (local["database"]["alembic_revision"], deployed["database"]["alembic_revision"]),
        "database.tables": (local["database"]["tables"], deployed["database"]["tables"]),
        "database.roles": (local["database"]["counts"]["roles"], deployed["database"]["counts"]["roles"]),
        "database.permissions": (local["database"]["counts"]["permissions"], deployed["database"]["counts"]["permissions"]),
        "database.role_permissions": (local["database"]["counts"]["role_permissions"], deployed["database"]["counts"]["role_permissions"]),
        "database.approved_data_counts": (
            {key: value for key, value in local["database"]["counts"].items() if key not in {"application_tables"}},
            {key: value for key, value in deployed["database"]["counts"].items() if key not in {"application_tables"}},
        ),
        "object_storage.logical_manifest_sha256": (
            local["object_storage"]["logical_manifest_sha256"],
            deployed["object_storage"]["logical_manifest_sha256"],
        ),
        "object_storage.version_count": (local["object_storage"]["version_count"], deployed["object_storage"]["version_count"]),
        "qdrant.vectors": (local["qdrant"]["vectors"], deployed["qdrant"]["vectors"]),
        "qdrant.logical_payload_sha256": (
            local["qdrant"]["logical_payload_sha256"],
            deployed["qdrant"]["logical_payload_sha256"],
        ),
        "qdrant.logical_point_count": (local["qdrant"]["logical_point_count"], deployed["qdrant"]["logical_point_count"]),
        "redis_policy": (local["redis_policy"], deployed["redis_policy"]),
    }
    failures = [name for name, values in checks.items() if values[0] != values[1]]
    for name, (expected, actual) in checks.items():
        print(f"{'PASS' if expected == actual else 'FAIL'} {name}")
    if failures:
        raise SystemExit("Deployment parity failed: " + ", ".join(failures))
    print("Deployment parity verified.")


if __name__ == "__main__":
    main()
