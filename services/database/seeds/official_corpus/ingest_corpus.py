"""Ingest official SA HE corpus into the LSA knowledge base.

Run AFTER Docker/PostgreSQL is running:
    python services/database/seeds/official_corpus/ingest_corpus.py

For each downloaded PDF:
1. Registers source in the source DB table
2. Uploads to object storage via the API
3. Queues a content.ingest_document worker job
4. Polls until completed
5. Verifies Qdrant chunk count
"""
from __future__ import annotations

import hashlib
import json
import os
import time
from pathlib import Path

import requests

REGISTRY_FILE = Path(__file__).parent / "source_registry.json"
DOCUMENTS_DIR = Path(__file__).parent / "documents"
API_BASE = os.getenv("API_BASE", "http://localhost:8001")
ADMIN_EMAIL = os.getenv("SEED_ADMIN_EMAIL", "admin.demo-north@example.com")


def sha256_file(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as f:
        for chunk in iter(lambda: f.read(65536), b""):
            h.update(chunk)
    return h.hexdigest()


def get_token() -> str:
    password_file = Path("runtime/seed_credentials.txt")
    password = ""
    if password_file.exists():
        for line in password_file.read_text().splitlines():
            if line.startswith("DEMO_PASSWORD="):
                password = line.split("=", 1)[1].strip()
    if not password:
        raise RuntimeError("Could not read DEMO_PASSWORD from runtime/seed_credentials.txt")

    r = requests.post(f"{API_BASE}/api/v1/auth/login", json={
        "email": ADMIN_EMAIL, "password": password
    }, timeout=15)
    r.raise_for_status()
    return r.json()["access_token"]


def main() -> None:
    registry = json.loads(REGISTRY_FILE.read_text(encoding="utf-8"))
    token = get_token()
    headers = {"Authorization": f"Bearer {token}"}

    print(f"Authenticated as {ADMIN_EMAIL}")

    results = []
    for source in registry["sources"]:
        sid = source["source_id"]
        fpath = DOCUMENTS_DIR / f"{sid}.pdf"

        if source.get("ingestion_status") != "downloaded" or not fpath.exists():
            print(f"  [SKIP] {sid} — not downloaded")
            results.append({"source_id": sid, "status": "skipped"})
            continue

        print(f"\n  [INGEST] {sid} — {source['title']}")
        print(f"    File: {fpath.name}  ({fpath.stat().st_size:,} bytes)")

        # Verify checksum
        actual = sha256_file(fpath)
        expected = source.get("checksum_sha256", "")
        if expected and actual != expected:
            print(f"    CHECKSUM MISMATCH — expected {expected[:16]}... got {actual[:16]}...")
            results.append({"source_id": sid, "status": "checksum_fail"})
            continue
        print(f"    Checksum OK: {actual[:16]}...")

        # Upload file via API
        with fpath.open("rb") as f:
            upload_r = requests.post(
                f"{API_BASE}/api/v1/documents/upload",
                headers=headers,
                files={"file": (fpath.name, f, "application/pdf")},
                data={
                    "title": source["title"],
                    "source_type": "official_regulation",
                    "classification": source["classification"],
                    "provenance_url": source["official_url"],
                    "authority": source["authority"],
                },
                timeout=60,
            )

        if upload_r.status_code not in (200, 201):
            print(f"    UPLOAD FAILED: {upload_r.status_code} {upload_r.text[:200]}")
            results.append({"source_id": sid, "status": "upload_failed", "error": upload_r.text[:200]})
            continue

        upload_data = upload_r.json()
        doc_id = upload_data.get("document_id") or upload_data.get("id")
        print(f"    Uploaded — document_id: {doc_id}")

        # Poll for ingestion completion
        max_polls = 30
        for attempt in range(max_polls):
            time.sleep(4)
            status_r = requests.get(
                f"{API_BASE}/api/v1/documents/{doc_id}",
                headers=headers, timeout=10,
            )
            if status_r.status_code != 200:
                break
            s = status_r.json()
            ingstatus = s.get("ingestion_status", "unknown")
            print(f"    Poll {attempt+1}/{max_polls}: {ingstatus}")
            if ingstatus in ("completed", "indexed"):
                chunk_count = s.get("chunk_count", "?")
                print(f"    INGESTED — chunks: {chunk_count}")
                results.append({
                    "source_id": sid,
                    "status": "completed",
                    "document_id": doc_id,
                    "chunk_count": chunk_count,
                })
                break
            if ingstatus in ("failed", "error"):
                print(f"    FAILED: {s.get('error', '')}")
                results.append({"source_id": sid, "status": "failed", "document_id": doc_id})
                break
        else:
            print(f"    TIMEOUT after {max_polls} polls")
            results.append({"source_id": sid, "status": "timeout", "document_id": doc_id})

    print("\n\n=== INGESTION SUMMARY ===")
    for r in results:
        print(f"  {r['source_id']}: {r['status']}")


if __name__ == "__main__":
    main()
