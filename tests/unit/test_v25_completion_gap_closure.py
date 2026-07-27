from __future__ import annotations

import json
from pathlib import Path

import httpx
import pytest
from jsonschema import Draft202012Validator

from services.api.app.ai.contracts import SourceCandidate
from services.api.app.ai.integrity import ClaimCitationVerifier
from services.api.app.ai.source_discovery import OpenAlexSourceDiscovery
from services.api.app.core.mfa import TOTP, generate_recovery_codes
from services.api.app.core.settings import Settings
from services.api.app.integrations.academic_systems import OneRosterCSVAdapter
from services.api.app.integrations.oidc import OIDCClient, OIDCDiscoveryDocument, pkce_pair
from services.api.app.main import app
from services.api.app.services.job_queue import ALLOWED_JOB_TYPES
from services.database.models import Base
from services.worker.handlers import HANDLERS

ROOT = Path(__file__).resolve().parents[2]


def test_v25_tables_and_routes_are_registered() -> None:
    expected_tables = {
        "iam.account_challenges", "iam.mfa_devices", "iam.mfa_recovery_codes",
        "iam.sso_connections", "iam.federated_identities", "governance.outbound_messages",
        "governance.integration_connections", "operations.integration_sync_runs",
        "governance.external_record_mappings", "privacy.legal_holds",
        "privacy.deletion_requests", "privacy.deletion_actions", "analytics.user_feedback",
        "analytics.evaluation_campaigns", "analytics.evaluation_responses",
        "governance.dataset_source_records", "operations.dataset_acquisition_runs",
    }
    assert len(Base.metadata.tables) == 124
    assert expected_tables <= set(Base.metadata.tables)
    paths = {route.path for route in app.routes}
    assert {
        "/api/v1/auth/password-reset/request", "/api/v1/auth/password-reset/confirm",
        "/api/v1/auth/sso/start", "/api/v1/auth/sso/callback", "/api/v1/auth/sso/exchange",
        "/api/v1/account/mfa/enrol", "/api/v1/integrations",
        "/api/v1/privacy/legal-holds", "/api/v1/privacy/deletion-requests",
        "/api/v1/feedback", "/api/v1/evaluation/campaigns", "/api/v1/data-sources",
    } <= paths
    assert app.version == "2.5.0"


def test_all_v25_job_types_have_real_handlers() -> None:
    assert ALLOWED_JOB_TYPES == set(HANDLERS)
    for job_type in {
        "communications.deliver_email", "integrations.sync",
        "privacy.execute_deletion", "data.acquire_dataset",
    }:
        assert job_type in HANDLERS
        assert HANDLERS[job_type].__name__ != "owner_machine_handler_required"


def test_totp_matches_rfc6238_sha1_vectors() -> None:
    settings = Settings(_env_file=None, mfa_totp_digits=8, mfa_totp_period_seconds=30)
    totp = TOTP(settings)
    secret = "GEZDGNBVGY3TQOJQGEZDGNBVGY3TQOJQ"
    assert totp.code(secret, at_time=59) == "94287082"
    assert totp.code(secret, at_time=1111111109) == "07081804"
    assert totp.verify(secret, "94287082", at_time=59, window=0)
    assert not totp.verify(secret, "00000000", at_time=59, window=0)


def test_recovery_codes_are_unique_and_human_readable() -> None:
    codes = generate_recovery_codes(10)
    assert len(codes) == len(set(codes)) == 10
    assert all(len(code.split("-")) == 2 for code in codes)


def test_oidc_authorization_uses_pkce_state_and_nonce() -> None:
    verifier, challenge = pkce_pair()
    assert verifier and challenge and verifier != challenge
    settings = Settings(_env_file=None)
    client = OIDCClient(
        issuer_url="https://id.example.edu", client_id="lsa", client_secret_reference=None,
        scopes=["openid", "profile", "email"], settings=settings,
    )
    discovery = OIDCDiscoveryDocument(
        issuer="https://id.example.edu",
        authorization_endpoint="https://id.example.edu/authorize",
        token_endpoint="https://id.example.edu/token",
        jwks_uri="https://id.example.edu/jwks",
        userinfo_endpoint=None,
    )
    url = client.authorization_url(
        discovery=discovery, redirect_uri="https://lsa.example.edu/callback",
        state="state-value", nonce="nonce-value", code_challenge=challenge,
    )
    assert "response_type=code" in url
    assert "code_challenge_method=S256" in url
    assert "state=state-value" in url
    assert "nonce=nonce-value" in url


@pytest.mark.asyncio
async def test_openalex_source_discovery_records_real_retrieval_metadata() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        assert request.url.path == "/works"
        return httpx.Response(200, json={"results": [{
            "id": "https://openalex.org/W1", "doi": "https://doi.org/10.1000/test",
            "title": "Constructive alignment in teaching", "publication_year": 2025,
            "type": "article", "relevance_score": 91.0,
            "authorships": [{"author": {"display_name": "A. Scholar"}}],
            "primary_location": {"landing_page_url": "https://doi.org/10.1000/test", "source": {"display_name": "Teaching Journal"}},
            "open_access": {"is_oa": True, "oa_status": "gold"},
        }]})
    async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as client:
        connector = OpenAlexSourceDiscovery(Settings(_env_file=None, openalex_enabled=True), client=client)
        records = await connector.discover("constructive alignment", limit=1)
    assert len(records) == 1
    assert records[0].doi == "10.1000/test"
    assert records[0].metadata["recorded_from_actual_retrieval"] is True
    assert records[0].metadata["openalex_id"] == "https://openalex.org/W1"


@pytest.mark.asyncio
async def test_oneroster_csv_adapter_stages_rows_without_vendor_lock_in() -> None:
    adapter = OneRosterCSVAdapter(
        base_url="", secret_reference=None,
        configuration={"csv_content": {"courses": "sourcedId,status,title\nc1,active,Engineering Design\n"}},
        settings=Settings(_env_file=None),
    )
    rows, cursor = await adapter.pull("courses")
    assert rows == [{"sourcedId": "c1", "status": "active", "title": "Engineering Design"}]
    assert cursor is None


def test_claim_citation_coverage_does_not_claim_entailment() -> None:
    source = SourceCandidate(
        source_key="s1", source_type="article", title="Evidence source", authors=[],
        publisher_or_organisation=None, publication_date="2025", canonical_url="https://example.org/source",
        doi=None, licence=None, reliability_tier="test", retrieved_by="test", retrieval_query="q", rank=1,
        relevance_score=1.0, metadata={"recorded_from_actual_retrieval": True},
    )
    result = ClaimCitationVerifier().verify(
        "Research indicates that active learning improves performance [S1]. A study shows a 20% gain.", [source]
    )
    assert result["claim_count"] == 2
    assert result["unsupported_claim_count"] == 1
    assert result["semantic_entailment_verified"] is False


def test_real_data_catalogue_is_schema_valid_and_contains_no_full_text() -> None:
    schema = json.loads((ROOT / "data/schemas/dataset_source_catalogue.schema.json").read_text())
    catalogue = json.loads((ROOT / "data/catalogues/verified_oer_and_metadata_sources_v2.5.json").read_text())
    Draft202012Validator.check_schema(schema)
    Draft202012Validator(schema).validate(catalogue)
    keys = {item["source_key"] for item in catalogue["sources"]}
    assert {"openalex_metadata", "crossref_metadata", "mit_ocw", "openstax"} <= keys
    mit = next(item for item in catalogue["sources"] if item["source_key"] == "mit_ocw")
    assert mit["commercial_use_allowed"] is False


def test_pwa_and_commercial_release_assets_exist() -> None:
    required = [
        "apps/web/public/manifest.webmanifest", "apps/web/public/sw.js",
        "apps/web/src/app/offline/page.tsx", "docs/legal/DATA_PROCESSING_AGREEMENT_TEMPLATE.md",
        "docs/legal/SERVICE_LEVEL_AGREEMENT_TEMPLATE.md", "docs/pilot/COMMERCIAL_PILOT_PLAN_V2.5.md",
        "packages/contracts/src/enterprise_integration_contracts.schema.json",
    ]
    assert all((ROOT / path).is_file() for path in required)

@pytest.mark.asyncio
async def test_in_memory_object_storage_deletes_exact_version() -> None:
    from uuid import uuid4
    from services.api.app.integrations.object_storage import InMemoryObjectStorage

    store = InMemoryObjectStorage()
    first = await store.put_bytes(
        tenant_id=uuid4(), object_key="tenant/document.txt", content=b"v1", media_type="text/plain"
    )
    second = await store.put_bytes(
        tenant_id=uuid4(), object_key="tenant/document.txt", content=b"v2", media_type="text/plain"
    )
    await store.delete_version(object_key=first.object_key, version_id=first.storage_version_id)
    with pytest.raises(KeyError):
        await store.get_bytes(object_key=first.object_key, version_id=first.storage_version_id)
    assert await store.get_bytes(object_key=second.object_key, version_id=second.storage_version_id) == b"v2"


def test_backup_executor_uses_tenant_scoped_paths(tmp_path: Path) -> None:
    from uuid import uuid4
    from services.worker.backup_execution import BackupExecutor

    settings = Settings(_env_file=None, backup_root_path=str(tmp_path))
    executor = BackupExecutor(settings)
    tenant_id, run_id = uuid4(), uuid4()
    directory = executor.run_directory(tenant_id=tenant_id, run_id=run_id, attempt=2)
    assert directory == tmp_path.resolve() / str(tenant_id) / str(run_id) / "attempt-002"
    assert directory.is_dir()


def test_v25_role_permissions_keep_admin_and_hod_independent() -> None:
    catalogue = json.loads((ROOT / "services/database/seeds/role_permissions.json").read_text())
    roles = {item["code"]: set(item["permissions"]) for item in catalogue["roles"]}
    assert "integrations.manage" in roles["institution_administrator"]
    assert "privacy.deletion.approve" in roles["institution_administrator"]
    assert "integrations.manage" not in roles["head_of_department"]
    assert "academic.assign_lecturer" in roles["head_of_department"]
    assert "academic.assign_lecturer" not in roles["institution_administrator"]


def test_sensitive_message_content_is_encrypted_at_rest() -> None:
    from services.api.app.core.sensitive_content import SensitiveContentProtector

    settings = Settings(
        _env_file=None,
        message_content_encryption_key="separate-message-key-for-tests",
    )
    protector = SensitiveContentProtector(settings)
    token_bearing_body = "Use https://example.edu/reset?token=raw-secret-token"
    ciphertext = protector.encrypt(token_bearing_body)
    assert token_bearing_body not in ciphertext
    assert protector.decrypt(ciphertext) == token_bearing_body


def test_oidc_transient_secret_protector_round_trip() -> None:
    from services.api.app.core.sensitive_content import SensitiveContentProtector

    settings = Settings(_env_file=None, message_content_encryption_key="oidc-transient-test-key")
    protector = SensitiveContentProtector(settings)
    verifier = "temporary-pkce-verifier"
    encrypted = protector.encrypt(verifier)
    assert verifier not in encrypted
    assert protector.decrypt(encrypted) == verifier


def test_outbound_url_policy_blocks_unsafe_targets() -> None:
    from services.api.app.core.outbound_url import validate_outbound_url

    settings = Settings(_env_file=None)
    assert validate_outbound_url("https://lms.example.edu", settings) == "https://lms.example.edu"
    with pytest.raises(ValueError, match="HTTPS"):
        validate_outbound_url("http://lms.example.edu", settings)
    with pytest.raises(ValueError, match="localhost"):
        validate_outbound_url("https://localhost:8443", settings)
    with pytest.raises(ValueError, match="private"):
        validate_outbound_url("https://10.0.0.5", settings)
    with pytest.raises(ValueError, match="embedded credentials"):
        validate_outbound_url("https://user:pass@lms.example.edu", settings)


def test_service_worker_does_not_cache_authenticated_html() -> None:
    worker = (ROOT / "apps/web/public/sw.js").read_text()
    assert 'event.request.mode === "navigate"' in worker
    assert 'caches.match("/offline")' in worker
    assert 'url.pathname.startsWith("/api/")' in worker
    assert 'cache.put(event.request, copy)' in worker
    assert 'url.pathname.startsWith("/_next/static/")' in worker
