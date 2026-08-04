"""Copy approved tenant-scoped Qdrant points to the deployed collection."""
from __future__ import annotations

import argparse
import asyncio
import json
import os
from pathlib import Path

import httpx


def cfg(prefix: str, name: str, default: str = "") -> str:
    value = os.getenv(f"{prefix}_{name}", default)
    if not value:
        raise SystemExit(f"{prefix}_{name} is required")
    return value


async def main_async(output: Path) -> None:
    source_url = cfg("SOURCE_QDRANT", "URL")
    destination_url = cfg("DESTINATION_QDRANT", "URL")
    source_collection = cfg("SOURCE_QDRANT", "COLLECTION")
    destination_collection = cfg("DESTINATION_QDRANT", "COLLECTION")
    approved = [item.strip() for item in os.getenv("APPROVED_TENANT_IDS", "").split(",") if item.strip()]
    if not approved:
        raise SystemExit("APPROVED_TENANT_IDS is required; copying every tenant is prohibited.")
    source_headers = {"api-key": os.getenv("SOURCE_QDRANT_API_KEY", "")} if os.getenv("SOURCE_QDRANT_API_KEY") else {}
    destination_headers = {"api-key": os.getenv("DESTINATION_QDRANT_API_KEY", "")} if os.getenv("DESTINATION_QDRANT_API_KEY") else {}
    filter_payload = {"must": [{"key": "tenant_id", "match": {"any": approved}}]}
    copied = 0
    offset = None
    point_ids: list[str] = []
    async with httpx.AsyncClient(base_url=source_url, headers=source_headers, timeout=120) as source, httpx.AsyncClient(base_url=destination_url, headers=destination_headers, timeout=120) as destination:
        source_info = await source.get(f"/collections/{source_collection}")
        source_info.raise_for_status()
        vectors = source_info.json()["result"]["config"]["params"]["vectors"]
        existing = await destination.get(f"/collections/{destination_collection}")
        if existing.status_code == 404:
            created = await destination.put(f"/collections/{destination_collection}", json={"vectors": vectors, "on_disk_payload": True})
            created.raise_for_status()
        else:
            existing.raise_for_status()
            destination_vectors = existing.json()["result"]["config"]["params"]["vectors"]
            if destination_vectors != vectors:
                raise RuntimeError(
                    "Destination Qdrant vector configuration does not match the source collection."
                )
        while True:
            body = {"limit": 256, "with_payload": True, "with_vector": True}
            if filter_payload:
                body["filter"] = filter_payload
            if offset is not None:
                body["offset"] = offset
            response = await source.post(f"/collections/{source_collection}/points/scroll", json=body)
            response.raise_for_status()
            result = response.json()["result"]
            points = result.get("points", [])
            if points:
                upsert = await destination.put(
                    f"/collections/{destination_collection}/points",
                    json={"points": points, "wait": True},
                )
                upsert.raise_for_status()
                copied += len(points)
                point_ids.extend(str(point["id"]) for point in points)
            offset = result.get("next_page_offset")
            if offset is None:
                break
        count_response = await destination.post(
            f"/collections/{destination_collection}/points/count",
            json={"filter": filter_payload, "exact": True},
        )
        count_response.raise_for_status()
        destination_count = int(count_response.json()["result"]["count"])
        if destination_count < copied:
            raise RuntimeError(
                f"Destination Qdrant verification failed: expected at least {copied}, got {destination_count}."
            )
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(
        json.dumps(
            {
                "schema_version": "1.1",
                "approved_tenant_ids": approved,
                "copied_points": copied,
                "destination_approved_point_count": destination_count,
                "point_ids": sorted(point_ids),
            },
            indent=2,
            sort_keys=True,
        ),
        encoding="utf-8",
    )
    print(f"Copied and verified {copied} Qdrant points.")


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--output", required=True)
    args = parser.parse_args()
    asyncio.run(main_async(Path(args.output)))


if __name__ == "__main__":
    main()
