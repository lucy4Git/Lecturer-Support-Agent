"""Copy approved S3 object versions and produce a database version-ID mapping.

The transfer is streamed through a spooled temporary file so large academic
assets are not held entirely in memory.  Only tenant-prefixed objects from the
explicit APPROVED_TENANT_IDS allowlist are eligible.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import os
import tempfile
from pathlib import Path

import boto3
from botocore.client import Config


def env(prefix: str, name: str) -> str:
    value = os.getenv(f"{prefix}_{name}", "")
    if not value:
        raise SystemExit(f"{prefix}_{name} is required")
    return value


def client(prefix: str):
    return boto3.client(
        "s3",
        endpoint_url=env(prefix, "ENDPOINT"),
        region_name=os.getenv(f"{prefix}_REGION", "us-east-1"),
        aws_access_key_id=env(prefix, "ACCESS_KEY"),
        aws_secret_access_key=env(prefix, "SECRET_KEY"),
        use_ssl=os.getenv(f"{prefix}_SECURE", "true").lower() in {"1", "true", "yes"},
        config=Config(signature_version="s3v4"),
    )


def versions(s3, bucket: str, approved_tenants: set[str]) -> list[dict]:
    paginator = s3.get_paginator("list_object_versions")
    rows: list[dict] = []
    for page in paginator.paginate(Bucket=bucket):
        for item in page.get("Versions", []):
            key = item["Key"]
            if not any(key.startswith(f"tenants/{tenant}/") for tenant in approved_tenants):
                continue
            rows.append(item)
    return sorted(rows, key=lambda item: (item["Key"], item["LastModified"]))


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--output", required=True)
    args = parser.parse_args()
    source = client("SOURCE_OBJECT_STORAGE")
    destination = client("DESTINATION_OBJECT_STORAGE")
    source_bucket = env("SOURCE_OBJECT_STORAGE", "BUCKET")
    destination_bucket = env("DESTINATION_OBJECT_STORAGE", "BUCKET")
    approved = {
        item.strip() for item in os.getenv("APPROVED_TENANT_IDS", "").split(",") if item.strip()
    }
    if not approved:
        raise SystemExit("APPROVED_TENANT_IDS is required; copying every tenant is prohibited.")
    destination.head_bucket(Bucket=destination_bucket)
    mapping: list[dict] = []
    for item in versions(source, source_bucket, approved):
        response = source.get_object(
            Bucket=source_bucket, Key=item["Key"], VersionId=item["VersionId"]
        )
        digest = hashlib.sha256()
        size = 0
        with tempfile.SpooledTemporaryFile(max_size=64 * 1024 * 1024) as content:
            while True:
                chunk = response["Body"].read(1024 * 1024)
                if not chunk:
                    break
                digest.update(chunk)
                size += len(chunk)
                content.write(chunk)
            checksum = digest.hexdigest()
            declared = response.get("Metadata", {}).get("sha256")
            if declared and declared != checksum:
                raise RuntimeError(
                    f"Source checksum mismatch for {item['Key']}:{item['VersionId']}"
                )
            if size != int(item["Size"]):
                raise RuntimeError(f"Source size mismatch for {item['Key']}:{item['VersionId']}")
            content.seek(0)
            stored = destination.put_object(
                Bucket=destination_bucket,
                Key=item["Key"],
                Body=content,
                ContentLength=size,
                ContentType=response.get("ContentType", "application/octet-stream"),
                Metadata={**response.get("Metadata", {}), "sha256": checksum},
            )
            destination_version = stored.get("VersionId")
            if not destination_version:
                raise RuntimeError("Destination storage did not return a version identifier.")
            head = destination.head_object(
                Bucket=destination_bucket, Key=item["Key"], VersionId=destination_version
            )
            if head.get("Metadata", {}).get("sha256") != checksum or int(head["ContentLength"]) != size:
                raise RuntimeError(f"Destination verification failed for {item['Key']}")
        mapping.append(
            {
                "object_key": item["Key"],
                "source_bucket": source_bucket,
                "source_version_id": item["VersionId"],
                "destination_bucket": destination_bucket,
                "destination_version_id": destination_version,
                "sha256": checksum,
                "size": size,
            }
        )
    canonical = json.dumps(
        sorted(
            ({"object_key": row["object_key"], "sha256": row["sha256"], "size": row["size"]} for row in mapping),
            key=lambda row: (row["object_key"], row["sha256"], row["size"]),
        ),
        sort_keys=True,
        separators=(",", ":"),
    ).encode()
    output = Path(args.output)
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(
        json.dumps(
            {
                "schema_version": "1.1",
                "approved_tenant_ids": sorted(approved),
                "logical_manifest_sha256": hashlib.sha256(canonical).hexdigest(),
                "objects": mapping,
            },
            indent=2,
            sort_keys=True,
        ),
        encoding="utf-8",
    )
    print(f"Copied {len(mapping)} approved object versions; mapping written to {output}.")


if __name__ == "__main__":
    main()
