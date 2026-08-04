"""Create a secret-free deployment parity manifest.

The manifest is intentionally based on identifiers, counts, migration revision,
object-version checksums, and Qdrant collection metadata. It never exports
passwords, tokens, or document content.
"""
from __future__ import annotations

import argparse
import asyncio
import hashlib
import json
import os
import subprocess
from datetime import datetime, timezone
from pathlib import Path

import boto3
import httpx
import psycopg
from botocore.client import Config

from services.api.app.core.settings import get_settings


def _plain_url(value: str) -> str:
    return value.replace("postgresql+psycopg://", "postgresql://", 1)


def _git_value(*args: str) -> str:
    try:
        return subprocess.check_output(["git", *args], text=True).strip()
    except Exception:
        return "unavailable"


def database_manifest(url: str) -> dict:
    queries = {
        "application_tables": """
            SELECT count(*) FROM information_schema.tables
             WHERE table_schema IN ('tenant','iam','academic','ingestion','content','conversation',
              'ai','source','review','audit','privacy','governance','analytics','operations')
               AND table_type='BASE TABLE'
        """,
        "roles": "SELECT count(*) FROM iam.roles",
        "permissions": "SELECT count(*) FROM iam.permissions",
        "role_permissions": "SELECT count(*) FROM iam.role_permissions",
        "institutions": "SELECT count(*) FROM tenant.institutions",
        "memberships": "SELECT count(*) FROM iam.memberships",
        "programmes": "SELECT count(*) FROM academic.programmes",
        "modules": "SELECT count(*) FROM academic.modules",
        "module_offerings": "SELECT count(*) FROM academic.module_offerings",
        "documents": "SELECT count(*) FROM content.documents",
        "document_versions": "SELECT count(*) FROM content.document_versions",
        "conversations": "SELECT count(*) FROM conversation.conversations",
        "generated_outputs": "SELECT count(*) FROM conversation.generated_outputs",
        "output_versions": "SELECT count(*) FROM conversation.output_versions",
    }
    with psycopg.connect(_plain_url(url)) as connection:
        row = connection.execute("SELECT version_num FROM alembic_version").fetchone()
        counts = {name: connection.execute(query).fetchone()[0] for name, query in queries.items()}
        tables = [
            f"{schema}.{table}"
            for schema, table in connection.execute(
                """SELECT table_schema, table_name FROM information_schema.tables
                     WHERE table_schema IN ('tenant','iam','academic','ingestion','content','conversation',
                       'ai','source','review','audit','privacy','governance','analytics','operations')
                       AND table_type='BASE TABLE' ORDER BY 1,2"""
            )
        ]
    return {"alembic_revision": row[0] if row else None, "counts": counts, "tables": tables}


def storage_manifest(settings) -> dict:
    client = boto3.client(
        "s3",
        endpoint_url=settings.object_storage_endpoint,
        region_name=settings.object_storage_region,
        aws_access_key_id=settings.object_storage_access_key.get_secret_value(),
        aws_secret_access_key=settings.object_storage_secret_key.get_secret_value(),
        use_ssl=settings.object_storage_secure,
        config=Config(signature_version="s3v4"),
    )
    objects: list[dict] = []
    key_marker = version_marker = None
    while True:
        kwargs = {"Bucket": settings.object_storage_bucket, "MaxKeys": 1000}
        if key_marker:
            kwargs["KeyMarker"] = key_marker
        if version_marker:
            kwargs["VersionIdMarker"] = version_marker
        response = client.list_object_versions(**kwargs)
        for item in response.get("Versions", []):
            head = client.head_object(
                Bucket=settings.object_storage_bucket,
                Key=item["Key"],
                VersionId=item["VersionId"],
            )
            objects.append(
                {
                    "key": item["Key"],
                    "version_id": item["VersionId"],
                    "size": item["Size"],
                    "sha256": head.get("Metadata", {}).get("sha256"),
                    "is_latest": bool(item.get("IsLatest")),
                }
            )
        if not response.get("IsTruncated"):
            break
        key_marker = response.get("NextKeyMarker")
        version_marker = response.get("NextVersionIdMarker")
    # Destination S3 providers assign new opaque version IDs.  Compare the
    # approved logical versions by object key, size, and verified content hash
    # instead of requiring provider-specific version IDs to match.
    logical_objects = sorted(
        ({"key": item["key"], "size": item["size"], "sha256": item["sha256"]} for item in objects),
        key=lambda item: (item["key"], item["sha256"] or "", item["size"]),
    )
    canonical = json.dumps(logical_objects, sort_keys=True, separators=(",", ":")).encode()
    return {
        "bucket": settings.object_storage_bucket,
        "versioning_mode": settings.object_storage_versioning_mode,
        "version_count": len(objects),
        "logical_manifest_sha256": hashlib.sha256(canonical).hexdigest(),
        "logical_objects": logical_objects,
        "objects": objects,
    }


async def qdrant_manifest(settings) -> dict:
    headers = {}
    if settings.qdrant_api_key:
        headers["api-key"] = settings.qdrant_api_key.get_secret_value()
    async with httpx.AsyncClient(base_url=settings.qdrant_url, headers=headers, timeout=60) as client:
        response = await client.get(f"/collections/{settings.qdrant_collection}")
        response.raise_for_status()
        result = response.json().get("result", {})
        offset = None
        logical_points: list[dict] = []
        while True:
            body: dict = {"limit": 256, "with_payload": True, "with_vector": False}
            if offset is not None:
                body["offset"] = offset
            page = await client.post(
                f"/collections/{settings.qdrant_collection}/points/scroll", json=body
            )
            page.raise_for_status()
            payload = page.json().get("result", {})
            for point in payload.get("points", []):
                metadata = point.get("payload") or {}
                logical_points.append(
                    {
                        "id": str(point.get("id")),
                        "tenant_id": str(metadata.get("tenant_id", "")),
                        "document_version_id": str(metadata.get("document_version_id", "")),
                        "document_chunk_id": str(
                            metadata.get("document_chunk_id", metadata.get("chunk_id", ""))
                        ),
                        "checksum": str(
                            metadata.get("checksum", metadata.get("sha256", ""))
                        ),
                    }
                )
            offset = payload.get("next_page_offset")
            if offset is None:
                break
    logical_points.sort(key=lambda item: (item["id"], item["tenant_id"], item["document_version_id"]))
    canonical = json.dumps(logical_points, sort_keys=True, separators=(",", ":")).encode()
    config = result.get("config", {})
    return {
        "collection": settings.qdrant_collection,
        "points_count": result.get("points_count"),
        "indexed_vectors_count": result.get("indexed_vectors_count"),
        "status": result.get("status"),
        "vectors": config.get("params", {}).get("vectors"),
        "logical_payload_sha256": hashlib.sha256(canonical).hexdigest(),
        "logical_point_count": len(logical_points),
    }


async def build(label: str) -> dict:
    settings = get_settings()
    return {
        "schema_version": "1.0",
        "label": label,
        "created_at": datetime.now(timezone.utc).isoformat(),
        "application": {
            "version": settings.deployment_version,
            "git_commit": _git_value("rev-parse", "HEAD"),
            "git_branch": _git_value("branch", "--show-current"),
        },
        "database": database_manifest(settings.migration_database_url.get_secret_value()),
        "object_storage": storage_manifest(settings),
        "qdrant": await qdrant_manifest(settings),
        "redis_policy": "clean_start_no_migration",
    }


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--label", required=True)
    parser.add_argument("--output", required=True)
    args = parser.parse_args()
    output = Path(args.output)
    output.parent.mkdir(parents=True, exist_ok=True)
    manifest = asyncio.run(build(args.label))
    output.write_text(json.dumps(manifest, indent=2, sort_keys=True), encoding="utf-8")
    print(f"Wrote parity manifest: {output}")


if __name__ == "__main__":
    main()
