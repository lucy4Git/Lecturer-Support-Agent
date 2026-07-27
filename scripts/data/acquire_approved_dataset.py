from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
from urllib.parse import urlparse

import httpx
from pydantic import BaseModel, Field, HttpUrl, model_validator


class Approval(BaseModel):
    status: str
    approved_by: str | None = None
    approved_at: str | None = None
    notes: str | None = None


class AcquisitionRequest(BaseModel):
    dataset_id: str = Field(pattern=r"^[a-z0-9][a-z0-9._-]{2,100}$")
    title: str
    source_url: HttpUrl
    publisher: str
    licence: str
    permitted_uses: list[str]
    expected_sha256: str | None = Field(default=None, pattern=r"^[a-f0-9]{64}$")
    maximum_bytes: int = Field(default=1_073_741_824, ge=1, le=10_737_418_240)
    contains_personal_data: bool = False
    contains_confidential_data: bool = False
    approval: Approval

    @model_validator(mode="after")
    def require_explicit_approval(self) -> "AcquisitionRequest":
        if self.approval.status != "approved":
            raise ValueError("Acquisition is blocked until approval.status is approved")
        if not self.approval.approved_by or not self.approval.approved_at:
            raise ValueError("Approved acquisitions require approved_by and approved_at")
        if self.contains_confidential_data:
            raise ValueError("The public acquisition tool cannot download confidential data")
        return self


def download(request: AcquisitionRequest, quarantine: Path) -> dict:
    parsed = urlparse(str(request.source_url))
    if parsed.scheme != "https":
        raise ValueError("Only HTTPS sources are permitted")
    quarantine.mkdir(parents=True, exist_ok=True)
    target = quarantine / f"{request.dataset_id}.download"
    digest = hashlib.sha256()
    size = 0
    with httpx.stream("GET", str(request.source_url), follow_redirects=True, timeout=60) as response:
        response.raise_for_status()
        with target.open("wb") as handle:
            for chunk in response.iter_bytes():
                size += len(chunk)
                if size > request.maximum_bytes:
                    handle.close()
                    target.unlink(missing_ok=True)
                    raise ValueError("Download exceeded approved maximum_bytes")
                digest.update(chunk)
                handle.write(chunk)
    actual = digest.hexdigest()
    if request.expected_sha256 and actual != request.expected_sha256:
        target.unlink(missing_ok=True)
        raise ValueError("Downloaded checksum does not match the approved manifest")
    record = {
        "dataset_id": request.dataset_id,
        "quarantine_path": str(target),
        "bytes": size,
        "sha256": actual,
        "status": "quarantined_download",
        "licence": request.licence,
        "permitted_uses": request.permitted_uses,
    }
    (quarantine / f"{request.dataset_id}.acquisition.json").write_text(
        json.dumps(record, indent=2), encoding="utf-8"
    )
    return record


def main() -> None:
    parser = argparse.ArgumentParser(description="Download one explicitly approved dataset into quarantine.")
    parser.add_argument("manifest", type=Path)
    parser.add_argument("--quarantine", type=Path, default=Path("data/quarantine"))
    args = parser.parse_args()
    request = AcquisitionRequest.model_validate_json(args.manifest.read_text(encoding="utf-8"))
    print(json.dumps(download(request, args.quarantine), indent=2))


if __name__ == "__main__":
    main()
