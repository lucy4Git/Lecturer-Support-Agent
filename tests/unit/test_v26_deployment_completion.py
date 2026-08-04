from __future__ import annotations

from pathlib import Path

import httpx
import pytest
import yaml

from services.api.app.core.settings import Settings
from services.api.app.ingestion.embeddings import (
    GeminiEmbeddingClient,
    OpenAIEmbeddingClient,
    build_embedding_client,
)
from services.api.app.integrations.object_storage import S3ObjectStorage
from services.database.models import Base


def test_access_request_table_and_migration_exist() -> None:
    assert "iam.institutional_access_requests" in Base.metadata.tables
    migration = Path(
        "services/database/migrations/versions/20260803_0012_v26_deployment_completion.py"
    )
    assert migration.exists()
    text = migration.read_text(encoding="utf-8")
    assert 'revision: str = "20260803_0012"' in text
    assert 'down_revision: str | None = "20260726_0011"' in text


def test_embedding_factory_supports_hosted_providers() -> None:
    gemini = build_embedding_client(
        Settings(
            _env_file=None,
            embedding_provider="google_gemini",
            google_gemini_api_key="test-key",
        ),
        client=httpx.AsyncClient(transport=httpx.MockTransport(lambda _: httpx.Response(500))),
    )
    assert isinstance(gemini, GeminiEmbeddingClient)
    openai = build_embedding_client(
        Settings(_env_file=None, embedding_provider="openai", openai_api_key="test-key"),
        client=httpx.AsyncClient(transport=httpx.MockTransport(lambda _: httpx.Response(500))),
    )
    assert isinstance(openai, OpenAIEmbeddingClient)


@pytest.mark.asyncio
async def test_gemini_embedding_dimension_is_enforced() -> None:
    async def handler(request: httpx.Request) -> httpx.Response:
        assert request.headers["x-goog-api-key"] == "test-key"
        return httpx.Response(200, json={"embeddings": [{"values": [0.1] * 8}]})

    client = httpx.AsyncClient(transport=httpx.MockTransport(handler))
    settings = Settings(
        _env_file=None,
        embedding_provider="google_gemini",
        google_gemini_api_key="test-key",
        embedding_dimension=8,
    )
    embedding = GeminiEmbeddingClient(settings, client)
    assert await embedding.embed(["synthetic teaching text"]) == [[0.1] * 8]
    await client.aclose()


@pytest.mark.asyncio
async def test_provider_enforced_storage_does_not_mutate_bucket_versioning() -> None:
    settings = Settings(_env_file=None, object_storage_versioning_mode="provider_enforced")
    storage = S3ObjectStorage.__new__(S3ObjectStorage)
    storage.settings = settings
    storage.bucket = "test-bucket"
    # boto methods execute in a thread, so use ordinary callable mock attributes.
    from unittest.mock import MagicMock

    sync_client = MagicMock()
    sync_client.head_bucket.return_value = {}
    sync_client.list_object_versions.return_value = {"Versions": []}
    storage.client = sync_client
    await storage.ensure_bucket()
    ready, status = await storage.probe_bucket()
    assert ready is True
    assert status == "ProviderEnforced"
    sync_client.put_bucket_versioning.assert_not_called()


def test_production_refuses_demo_seed() -> None:
    with pytest.raises(ValueError, match="demo"):
        Settings(
            _env_file=None,
            environment="production",
            enable_demo_seed=True,
            ai_enable_development_mock=False,
            rate_limit_fail_closed=True,
            malware_scan_enabled=True,
            malware_scan_fail_closed=True,
            metrics_enabled=False,
            backup_storage_encryption_attested=True,
            mfa_secret_encryption_key="x" * 32,
            message_content_encryption_key="y" * 32,
            embedding_provider="google_gemini",
            google_gemini_api_key="test",
            database_url="postgresql+psycopg://lsa_app:secure@db.example/test",
            auth_database_url="postgresql+psycopg://lsa_auth:secure@db.example/test",
            migration_database_url="postgresql+psycopg://owner:secure@db.example/test",
            worker_database_url="postgresql+psycopg://lsa_worker:secure@db.example/test",
            trusted_hosts="api.example.com",
            cors_allowed_origins="https://app.example.com",
            jwt_secret_key="z" * 64,
        )


def test_render_blueprints_share_cryptographic_secrets_and_delay_staging_seed() -> None:
    staging = yaml.safe_load(Path("render.yaml").read_text(encoding="utf-8"))
    production = yaml.safe_load(Path("render.production.yaml").read_text(encoding="utf-8"))
    assert [group["name"] for group in staging["envVarGroups"]] == [
        "lsa-staging-generated-secrets", "lsa-staging-hosted-configuration"
    ]
    assert [group["name"] for group in production["envVarGroups"]] == [
        "lsa-production-generated-secrets", "lsa-production-hosted-configuration"
    ]
    api = next(service for service in staging["services"] if service["type"] == "web")
    worker = next(service for service in staging["services"] if service["type"] == "worker")
    expected_groups = [
        {"fromGroup": "lsa-staging-generated-secrets"},
        {"fromGroup": "lsa-staging-hosted-configuration"},
    ]
    assert api["envVars"][:2] == expected_groups
    assert worker["envVars"][:2] == expected_groups
    values = {item.get("key"): item.get("value") for item in api["envVars"] if "key" in item}
    assert values["ENABLE_DEMO_SEED"] == "false"


def test_staging_seed_requires_secret_manager_password() -> None:
    seed = Path("services/database/seeds/seed_foundation.py").read_text(encoding="utf-8")
    assert "Staging demonstration seeding requires SEED_DEMO_PASSWORD" in seed
    assert "Synthetic demonstration seeding is prohibited in production" in seed
