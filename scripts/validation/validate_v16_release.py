from __future__ import annotations

import ast
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]

REQUIRED = [
    "services/database/models/ingestion.py",
    "services/database/migrations/versions/20260725_0003_v16_ingestion_retrieval.py",
    "services/api/app/ingestion/archive.py",
    "services/api/app/ingestion/parsers.py",
    "services/api/app/ingestion/chunking.py",
    "services/api/app/ingestion/embeddings.py",
    "services/api/app/services/document_ingestion.py",
    "services/api/app/services/document_retrieval.py",
    "services/api/app/services/document_versioning.py",
    "docs/implementation/PHASE_5_V1.6_IMPLEMENTATION_REPORT.md",
]


def main() -> None:
    missing = [item for item in REQUIRED if not (ROOT / item).is_file()]
    if missing:
        raise SystemExit(f"Missing v1.6 files: {missing}")
    for path in ROOT.rglob("*.py"):
        ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
    for path in ROOT.rglob("*.json"):
        json.loads(path.read_text(encoding="utf-8"))
    ingestion = (ROOT / "services/database/models/ingestion.py").read_text(encoding="utf-8")
    for model in ["IngestionJob", "ExtractedContent", "DocumentChunk", "DocumentVersionTransition", "InstitutionalRetrievalTrace"]:
        assert f"class {model}" in ingestion
    workspace = (ROOT / "apps/web/src/components/workspace-shell.tsx").read_text(encoding="utf-8")
    assert "BulkUploadForm" in workspace
    assert "pendingAttachments" in workspace
    assert "Production upload interface in v1.7" not in workspace
    document_routes = (ROOT / "services/api/app/routes/documents.py").read_text(encoding="utf-8")
    assert "transition_document_version_status" in document_routes
    versioning = (ROOT / "services/api/app/services/document_versioning.py").read_text(encoding="utf-8")
    assert "DOCUMENT_VERSION_TRANSITIONS" in versioning
    assert "permission_code=\"content.upload\"" in versioning
    print("v1.6 static release validation passed")


if __name__ == "__main__":
    main()
