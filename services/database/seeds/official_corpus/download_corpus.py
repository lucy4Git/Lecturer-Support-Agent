"""Download official South African HE corpus documents.

Downloads authoritative documents from official government and statutory sources.
Records checksums and updates source registry with retrieval metadata.

Usage:
    python services/database/seeds/official_corpus/download_corpus.py
"""
from __future__ import annotations

import hashlib
import json
import ssl
import time
import urllib.request
from datetime import datetime, timezone
from pathlib import Path

# Some official South African government sites have SSL chain issues on Windows.
# We create a permissive context only for known official government domains.
_TRUSTED_GOV_DOMAINS = {"saqa.org.za", "che.ac.za", "gov.za", "dhet.gov.za", "justice.gov.za"}

def _ssl_ctx(url: str) -> ssl.SSLContext | None:
    from urllib.parse import urlparse
    host = urlparse(url).hostname or ""
    if any(host.endswith(d) for d in _TRUSTED_GOV_DOMAINS):
        ctx = ssl.create_default_context()
        ctx.check_hostname = False
        ctx.verify_mode = ssl.CERT_NONE
        return ctx
    return None

REGISTRY_FILE = Path(__file__).parent / "source_registry.json"
OUTPUT_DIR = Path(__file__).parent / "documents"

HEADERS = {
    "User-Agent": (
        "LecturerSupportAgent/1.0 "
        "(Academic research corpus; contact: admin@lsa.example.com)"
    ),
}


def sha256_file(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as f:
        for chunk in iter(lambda: f.read(65536), b""):
            h.update(chunk)
    return h.hexdigest()


def download(url: str, dest: Path) -> tuple[bool, str]:
    """Download url to dest. Returns (ok, error_or_empty)."""
    try:
        req = urllib.request.Request(url, headers=HEADERS)
        ctx = _ssl_ctx(url)
        with urllib.request.urlopen(req, timeout=60, context=ctx) as resp:
            content = resp.read()
        dest.write_bytes(content)
        return True, ""
    except Exception as exc:
        return False, str(exc)


def main() -> None:
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    registry = json.loads(REGISTRY_FILE.read_text(encoding="utf-8"))
    now = datetime.now(timezone.utc).isoformat()
    updated = False

    for source in registry["sources"]:
        sid = source["source_id"]
        url = source["official_url"]
        filename = OUTPUT_DIR / f"{sid}.pdf"

        if source.get("ingestion_status") == "downloaded" and filename.exists():
            print(f"  [SKIP] {sid} already downloaded ({filename.stat().st_size:,} bytes)")
            continue
        # Reset failed entries for retry
        if source.get("ingestion_status") == "download_failed":
            source.pop("download_error", None)

        print(f"  [DOWNLOAD] {sid}")
        print(f"    URL: {url}")

        ok, err = download(url, filename)
        source["retrieval_date"] = now

        if ok:
            checksum = sha256_file(filename)
            size = filename.stat().st_size
            source["checksum_sha256"] = checksum
            source["file_size_bytes"] = size
            source["malware_state"] = "pending_scan"
            source["ingestion_status"] = "downloaded"
            print(f"    OK  size={size:,} bytes  sha256={checksum[:16]}...")
            updated = True
        else:
            source["ingestion_status"] = "download_failed"
            source["download_error"] = err
            print(f"    FAIL: {err}")

        time.sleep(2)  # polite crawl delay

    if updated:
        REGISTRY_FILE.write_text(
            json.dumps(registry, indent=2, ensure_ascii=False),
            encoding="utf-8",
        )
        print(f"\nRegistry updated: {REGISTRY_FILE}")
    else:
        print("\nNo new downloads.")


if __name__ == "__main__":
    main()
