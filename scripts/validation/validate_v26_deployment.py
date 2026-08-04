from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))


def require(path: str) -> Path:
    item = ROOT / path
    assert item.exists(), f"Missing required v2.6 file: {path}"
    return item


def main() -> None:
    required = [
        "DEPLOYMENT_QUICKSTART.md",
        "render.yaml",
        "render.production.yaml",
        "apps/web/vercel.json",
        "scripts/deployment/predeploy.py",
        "scripts/deployment/bootstrap_database_roles.py",
        "scripts/deployment/validate_deployment_configuration.py",
        "scripts/deployment/validate_approved_export_source.py",
        "scripts/deployment/create_parity_manifest.py",
        "scripts/deployment/verify_parity.py",
        "scripts/deployment/create_safe_release.py",
        "scripts/deployment/Export-ApprovedLocalData.ps1",
        "scripts/deployment/Import-ApprovedData.ps1",
        "scripts/deployment/migrate_object_versions.py",
        "scripts/deployment/migrate_qdrant.py",
        "services/database/migrations/versions/20260803_0012_v26_deployment_completion.py",
        "docs/operations/VERCEL_RENDER_NEON_DEPLOYMENT.md",
        "docs/operations/DEPLOYMENT_PARITY_RUNBOOK.md",
        "docs/security/GITHUB_AND_DEPLOYMENT_SECURITY.md",
    ]
    for item in required:
        require(item)

    staging = yaml.safe_load(require("render.yaml").read_text(encoding="utf-8"))
    production = yaml.safe_load(require("render.production.yaml").read_text(encoding="utf-8"))
    assert len(staging["services"]) == 4
    assert len(production["services"]) == 4
    assert any(service["type"] == "worker" for service in staging["services"])
    assert any(service["type"] == "keyvalue" for service in staging["services"])
    assert [group["name"] for group in staging["envVarGroups"]] == [
        "lsa-staging-generated-secrets", "lsa-staging-hosted-configuration"
    ]
    assert [group["name"] for group in production["envVarGroups"]] == [
        "lsa-production-generated-secrets", "lsa-production-hosted-configuration"
    ]
    shared_keys = {item["key"] for item in staging["envVarGroups"][0]["envVars"]}
    assert shared_keys == {
        "JWT_SECRET_KEY", "MFA_SECRET_ENCRYPTION_KEY",
        "MESSAGE_CONTENT_ENCRYPTION_KEY", "METRICS_TOKEN",
    }
    staging_api = next(service for service in staging["services"] if service["type"] == "web")
    staging_values = {item.get("key"): item.get("value") for item in staging_api["envVars"] if "key" in item}
    assert staging_values["ENABLE_DEMO_SEED"] == "false"
    assert staging_api["envVars"][:2] == [
        {"fromGroup": "lsa-staging-generated-secrets"},
        {"fromGroup": "lsa-staging-hosted-configuration"},
    ]
    assert not any(item.get("sync") is False for item in staging_api["envVars"] if isinstance(item, dict))

    vercel = json.loads(require("apps/web/vercel.json").read_text(encoding="utf-8"))
    assert vercel["framework"] == "nextjs"
    assert vercel["installCommand"] == "npm ci"

    migration = require(
        "services/database/migrations/versions/20260803_0012_v26_deployment_completion.py"
    ).read_text(encoding="utf-8")
    assert 'revision: str = "20260803_0012"' in migration
    assert 'down_revision: str | None = "20260726_0011"' in migration

    settings = require("services/api/app/core/settings.py").read_text(encoding="utf-8")
    for token in (
        "object_storage_versioning_mode",
        "google_gemini_embedding_model",
        "openai_embedding_model",
        "enable_demo_seed",
        "Production must keep ENABLE_DEMO_SEED disabled",
    ):
        assert token in settings

    seed = require("services/database/seeds/seed_foundation.py").read_text(encoding="utf-8")
    assert "Synthetic demonstration seeding is prohibited in production" in seed
    assert "ENABLE_DEMO_SEED" in seed

    embedding = require("services/api/app/ingestion/embeddings.py").read_text(encoding="utf-8")
    assert "class GeminiEmbeddingClient" in embedding
    assert "class OpenAIEmbeddingClient" in embedding
    assert "def build_embedding_client" in embedding

    from services.api.app.main import app
    from services.database.models import Base

    assert app.version == "2.6.0"
    paths = set(app.openapi()["paths"])
    assert "/api/v1/auth/access-requests" in paths
    assert "/api/v1/users/access-requests" in paths
    assert "iam.institutional_access_requests" in Base.metadata.tables
    assert len(Base.metadata.tables) == 125

    env_file = ROOT / ".env"
    if env_file.exists():
        # An owner-machine workspace may contain an ignored .env, but release
        # validation must prove it is not tracked. The safe archive excludes it.
        tracked = subprocess.run(
            ["git", "ls-files", "--error-unmatch", ".env"],
            cwd=ROOT, capture_output=True, text=True, check=False,
        )
        assert tracked.returncode != 0, "Real .env must never be tracked."
    print("v2.6 deployment completion validation passed.")


if __name__ == "__main__":
    main()
