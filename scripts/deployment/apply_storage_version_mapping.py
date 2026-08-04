"""Verify destination object versions, then update imported PostgreSQL metadata."""
from __future__ import annotations

import argparse
import json
import os
from pathlib import Path

import boto3
import psycopg
from botocore.client import Config


def _required(name: str) -> str:
    value = os.getenv(name, "")
    if not value:
        raise SystemExit(f"{name} is required.")
    return value


def _storage_client():
    return boto3.client(
        "s3",
        endpoint_url=_required("DESTINATION_OBJECT_STORAGE_ENDPOINT"),
        region_name=os.getenv("DESTINATION_OBJECT_STORAGE_REGION", "us-east-1"),
        aws_access_key_id=_required("DESTINATION_OBJECT_STORAGE_ACCESS_KEY"),
        aws_secret_access_key=_required("DESTINATION_OBJECT_STORAGE_SECRET_KEY"),
        use_ssl=os.getenv("DESTINATION_OBJECT_STORAGE_SECURE", "true").lower()
        in {"1", "true", "yes"},
        config=Config(signature_version="s3v4"),
    )


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("mapping")
    parser.add_argument("--approved", action="store_true")
    args = parser.parse_args()
    if not args.approved:
        raise SystemExit("Use --approved only after validating the object migration mapping.")
    url = os.getenv("MIGRATION_DATABASE_URL", "").replace(
        "postgresql+psycopg://", "postgresql://", 1
    )
    if not url:
        raise SystemExit("MIGRATION_DATABASE_URL is required.")
    payload = json.loads(Path(args.mapping).read_text(encoding="utf-8"))
    items = payload["objects"]
    storage = _storage_client()

    for item in items:
        head = storage.head_object(
            Bucket=item["destination_bucket"],
            Key=item["object_key"],
            VersionId=item["destination_version_id"],
        )
        actual_hash = head.get("Metadata", {}).get("sha256")
        if actual_hash != item["sha256"] or int(head["ContentLength"]) != int(item["size"]):
            raise RuntimeError(f"Destination object verification failed for {item['object_key']}")

    with psycopg.connect(url) as connection:
        for item in items:
            result = connection.execute(
                """UPDATE content.storage_objects
                      SET bucket_name=%s, storage_version_id=%s
                    WHERE object_key=%s AND bucket_name=%s AND storage_version_id=%s""",
                (
                    item["destination_bucket"],
                    item["destination_version_id"],
                    item["object_key"],
                    item["source_bucket"],
                    item["source_version_id"],
                ),
            )
            if result.rowcount != 1:
                raise RuntimeError(
                    f"Expected one storage row for {item['object_key']}; got {result.rowcount}"
                )
    print(f"Verified and applied {len(items)} storage-version mappings.")


if __name__ == "__main__":
    main()
