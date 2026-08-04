from __future__ import annotations

from functools import lru_cache

from pydantic import Field, SecretStr, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Runtime configuration loaded from environment variables.

    Secret values are never represented in repository configuration files. The
    safe ``.env.example`` contains only variable names and development defaults.
    """

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",
    )

    app_name: str = "Lecturer Support Agent API"
    environment: str = "development"
    debug: bool = False
    api_prefix: str = "/api/v1"
    public_app_url: str = "http://localhost:3000"

    database_url: SecretStr = SecretStr(
        "postgresql+psycopg://lsa_app:change-me@localhost:5432/lecturer_support_agent"
    )
    auth_database_url: SecretStr = SecretStr(
        "postgresql+psycopg://lsa_auth:change-me@localhost:5432/lecturer_support_agent"
    )
    migration_database_url: SecretStr = SecretStr(
        "postgresql+psycopg://lsa_owner:change-me@localhost:5432/lecturer_support_agent"
    )
    worker_database_url: SecretStr = SecretStr(
        "postgresql+psycopg://lsa_worker:change-me@localhost:5432/lecturer_support_agent"
    )

    redis_url: SecretStr = SecretStr("redis://localhost:6379/0")
    qdrant_url: str = "http://localhost:6333"
    qdrant_api_key: SecretStr | None = None
    qdrant_collection: str = "lecturer_support_documents"

    object_storage_endpoint: str = "http://localhost:9000"
    object_storage_region: str = "us-east-1"
    object_storage_access_key: SecretStr = SecretStr("lsa-development")
    object_storage_secret_key: SecretStr = SecretStr("change-me")
    object_storage_bucket: str = "lecturer-support-agent"
    object_storage_secure: bool = False
    object_storage_versioning_mode: str = "managed"

    jwt_issuer: str = "lecturer-support-agent"
    jwt_audience: str = "lecturer-support-agent-api"
    jwt_algorithm: str = "HS256"
    jwt_secret_key: SecretStr | None = SecretStr("replace-with-at-least-32-random-bytes")
    jwt_private_key: str | None = None
    jwt_public_key: str | None = None
    jwt_clock_skew_seconds: int = Field(default=30, ge=0, le=300)
    access_token_minutes: int = Field(default=15, ge=5, le=60)
    refresh_token_days: int = Field(default=14, ge=1, le=90)

    development_header_auth: bool = False
    expose_development_invitation_tokens: bool = False
    invitation_expiry_hours: int = Field(default=72, ge=1, le=720)

    password_min_length: int = Field(default=12, ge=10, le=128)
    password_require_mixed_classes: bool = True
    password_argon2_time_cost: int = Field(default=3, ge=2, le=10)
    password_argon2_memory_kib: int = Field(default=65536, ge=32768, le=1048576)
    password_argon2_parallelism: int = Field(default=4, ge=1, le=16)
    maximum_failed_login_attempts: int = Field(default=5, ge=3, le=20)
    account_lock_minutes: int = Field(default=15, ge=1, le=1440)

    # Provider-neutral AI conversation engine. Real keys stay in .env or a
    # production secret manager and are represented as SecretStr values.
    ai_routing_mode: str = "capability_policy_router"
    ai_default_provider: str = "auto"
    ai_fallback_order: str = "ollama,anthropic,openai,google_gemini,deepseek"
    ai_request_timeout_seconds: int = Field(default=90, ge=10, le=600)
    ai_max_output_tokens: int = Field(default=4096, ge=256, le=32768)
    ai_temperature: float = Field(default=0.2, ge=0.0, le=2.0)
    ai_enable_development_mock: bool = True
    ai_require_local_for_restricted: bool = True
    ai_max_conversation_messages: int = Field(default=24, ge=2, le=200)

    openai_api_key: SecretStr | None = None
    openai_base_url: str = "https://api.openai.com/v1"
    openai_default_model: str = ""
    anthropic_api_key: SecretStr | None = None
    anthropic_base_url: str = "https://api.anthropic.com"
    anthropic_default_model: str = ""
    anthropic_api_version: str = "2023-06-01"
    google_gemini_api_key: SecretStr | None = None
    google_gemini_base_url: str = "https://generativelanguage.googleapis.com"
    google_gemini_default_model: str = ""
    deepseek_api_key: SecretStr | None = None
    deepseek_base_url: str = "https://api.deepseek.com"
    deepseek_default_model: str = ""
    ollama_base_url: str = "http://localhost:11434"
    ollama_default_model: str = "qwen3:8b"
    ollama_embedding_model: str = "nomic-embed-text-v2-moe"
    google_gemini_embedding_model: str = "gemini-embedding-2"
    openai_embedding_model: str = "text-embedding-3-small"

    source_discovery_enabled: bool = True
    crossref_base_url: str = "https://api.crossref.org"
    crossref_contact_email: str = ""
    source_discovery_max_results: int = Field(default=5, ge=0, le=10)
    source_http_timeout_seconds: int = Field(default=15, ge=5, le=60)

    # v1.6 ingestion, chunking, embedding, and authorised retrieval.
    ingestion_auto_process_uploads: bool = True
    ingestion_chunk_characters: int = Field(default=3200, ge=400, le=20000)
    ingestion_chunk_overlap_characters: int = Field(default=320, ge=0, le=5000)
    ingestion_max_archive_entries: int = Field(default=500, ge=1, le=10000)
    ingestion_max_archive_uncompressed_bytes: int = Field(default=2_147_483_648, ge=1)
    ingestion_max_archive_member_bytes: int = Field(default=1_073_741_824, ge=1)
    embedding_provider: str = "ollama"
    embedding_dimension: int = Field(default=768, ge=8, le=8192)
    embedding_timeout_seconds: int = Field(default=120, ge=10, le=600)
    retrieval_max_chunks: int = Field(default=6, ge=1, le=20)
    retrieval_max_excerpt_characters: int = Field(default=2200, ge=200, le=10000)
    retrieval_min_score: float | None = Field(default=None, ge=0.0, le=1.0)

    # v1.7 production teaching-output workflows and export controls.
    output_max_edit_characters: int = Field(default=500_000, ge=1_000, le=2_000_000)
    export_max_bytes: int = Field(default=52_428_800, ge=1_048_576, le=536_870_912)
    export_allowed_formats: str = "markdown,html,docx,pdf,pptx,xlsx"
    assessment_require_module_context_for_release: bool = True
    assessment_block_student_copy_with_answers: bool = True

    # v2.3 production hardening, operational safety, and reliability.
    log_level: str = "INFO"
    json_logs: bool = True
    trusted_hosts: str = "localhost,127.0.0.1"
    cors_allowed_origins: str = "http://localhost:3000"
    content_security_policy: str = (
        "default-src 'self'; base-uri 'self'; frame-ancestors 'none'; "
        "object-src 'none'; img-src 'self' data: blob:; media-src 'self' blob:; "
        "connect-src 'self' http://localhost:8000 http://localhost:11434; "
        "script-src 'self'; style-src 'self' 'unsafe-inline'; form-action 'self'"
    )
    maximum_request_bytes: int = Field(default=1_126_170_624, ge=1_048_576)
    rate_limit_enabled: bool = True
    api_rate_limit_per_minute: int = Field(default=240, ge=10, le=100_000)
    auth_rate_limit_per_minute: int = Field(default=20, ge=3, le=10_000)
    rate_limit_fail_closed: bool = False
    metrics_enabled: bool = True
    metrics_token: SecretStr | None = None
    readiness_probe_timeout_seconds: int = Field(default=5, ge=1, le=60)
    readiness_require_ollama: bool = False
    malware_scan_enabled: bool = False
    malware_scan_fail_closed: bool = False
    malware_scan_timeout_seconds: int = Field(default=30, ge=1, le=300)
    clamav_host: str = "localhost"
    clamav_port: int = Field(default=3310, ge=1, le=65535)
    background_worker_poll_seconds: float = Field(default=2.0, ge=0.1, le=60.0)
    background_job_lease_seconds: int = Field(default=120, ge=30, le=3600)

    # v2.5 account security, messaging, enterprise integrations, and data preparation.
    password_reset_expiry_minutes: int = Field(default=30, ge=5, le=1440)
    email_verification_expiry_hours: int = Field(default=24, ge=1, le=720)
    mfa_totp_issuer: str = "Lecturer Support Agent"
    mfa_totp_period_seconds: int = Field(default=30, ge=15, le=120)
    mfa_totp_digits: int = Field(default=6, ge=6, le=8)
    mfa_recovery_code_count: int = Field(default=10, ge=5, le=20)
    mfa_secret_encryption_key: SecretStr | None = None
    message_content_encryption_key: SecretStr | None = None

    email_delivery_enabled: bool = False
    email_provider: str = "smtp"
    email_from_address: str = "no-reply@example.invalid"
    email_from_name: str = "Lecturer Support Agent"
    smtp_host: str = "localhost"
    smtp_port: int = Field(default=1025, ge=1, le=65535)
    smtp_username: str | None = None
    smtp_password: SecretStr | None = None
    smtp_use_tls: bool = False
    smtp_use_starttls: bool = False

    oidc_http_timeout_seconds: int = Field(default=20, ge=5, le=120)
    oidc_state_expiry_minutes: int = Field(default=10, ge=2, le=60)
    integration_http_timeout_seconds: int = Field(default=60, ge=5, le=600)
    integration_max_records_per_sync: int = Field(default=10_000, ge=1, le=1_000_000)
    outbound_http_allow_insecure: bool = False
    outbound_http_allow_private_networks: bool = False
    outbound_http_allowed_hosts: str = ""

    openalex_enabled: bool = True
    openalex_base_url: str = "https://api.openalex.org"
    openalex_api_key: SecretStr | None = None
    openalex_contact_email: str = ""
    source_claim_verification_required_for_high_stakes: bool = True

    deletion_require_second_approver: bool = True
    deletion_allow_hard_delete: bool = False
    legal_hold_default_review_days: int = Field(default=365, ge=1, le=3650)

    # v2.5 backup execution and non-destructive restore-drill controls.
    backup_root_path: str = "runtime/backups"
    pg_dump_executable: str = "pg_dump"
    pg_restore_executable: str = "pg_restore"
    backup_component_timeout_seconds: int = Field(default=600, ge=30, le=86_400)
    backup_storage_encryption_attested: bool = False
    restore_drill_executable: str | None = None

    enable_demo_seed: bool = False
    deployment_version: str = "2.6.0"

    maximum_upload_bytes: int = Field(default=1_073_741_824, ge=1)
    allowed_upload_media_types: list[str] = Field(
        default_factory=lambda: [
            "application/pdf",
            "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
            "application/vnd.openxmlformats-officedocument.presentationml.presentation",
            "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
            "text/plain",
            "text/csv",
            "image/png",
            "image/jpeg",
            "audio/mpeg",
            "video/mp4",
            "application/zip",
        ]
    )

    @model_validator(mode="after")
    def validate_production_security(self) -> "Settings":
        if self.environment.lower() == "production":
            if self.development_header_auth or self.expose_development_invitation_tokens:
                raise ValueError("Development authentication features must be disabled in production.")
            if self.enable_demo_seed:
                raise ValueError("Production must keep ENABLE_DEMO_SEED disabled.")
            if self.ai_enable_development_mock:
                raise ValueError("The development AI mock must be disabled in production.")
            if not self.rate_limit_enabled or not self.rate_limit_fail_closed:
                raise ValueError("Production rate limiting must be enabled and fail closed.")
            if not self.malware_scan_enabled or not self.malware_scan_fail_closed:
                raise ValueError("Production uploads require fail-closed malware scanning.")
            if self.metrics_enabled and not self.metrics_token:
                raise ValueError("Production metrics exposure requires METRICS_TOKEN.")
            if not self.backup_storage_encryption_attested:
                raise ValueError("Production backup storage requires an explicit encryption-at-rest attestation.")
            if not self.mfa_secret_encryption_key:
                raise ValueError("Production MFA requires a dedicated MFA_SECRET_ENCRYPTION_KEY.")
            if self.embedding_provider == "ollama" and self.readiness_require_ollama is False:
                raise ValueError("Production Ollama embeddings require an explicitly reachable private Ollama service.")
            if self.embedding_provider in {"gemini", "google_gemini"} and not self.google_gemini_api_key:
                raise ValueError("Production Gemini embeddings require GOOGLE_GEMINI_API_KEY.")
            if self.embedding_provider == "openai" and not self.openai_api_key:
                raise ValueError("Production OpenAI embeddings require OPENAI_API_KEY.")
            if self.object_storage_versioning_mode not in {"managed", "provider_enforced"}:
                raise ValueError("OBJECT_STORAGE_VERSIONING_MODE must be managed or provider_enforced.")
            if not self.message_content_encryption_key:
                raise ValueError("Production queued messages require MESSAGE_CONTENT_ENCRYPTION_KEY.")
            database_values = {
                "DATABASE_URL": self.database_url.get_secret_value(),
                "AUTH_DATABASE_URL": self.auth_database_url.get_secret_value(),
                "MIGRATION_DATABASE_URL": self.migration_database_url.get_secret_value(),
                "WORKER_DATABASE_URL": self.worker_database_url.get_secret_value(),
            }
            for name, value in database_values.items():
                if "change-me" in value or "change-" in value:
                    raise ValueError(f"Production {name} still contains a development placeholder.")
            allowed_hosts = {item.strip() for item in self.trusted_hosts.split(",") if item.strip()}
            if not allowed_hosts or allowed_hosts <= {"localhost", "127.0.0.1"}:
                raise ValueError("Production TRUSTED_HOSTS must include the deployed host name.")
            origins = {item.strip() for item in self.cors_allowed_origins.split(",") if item.strip()}
            if not origins or any(origin == "*" for origin in origins):
                raise ValueError("Production CORS_ALLOWED_ORIGINS must be explicit.")
            if self.jwt_algorithm.startswith("HS"):
                secret = self.jwt_secret_key.get_secret_value() if self.jwt_secret_key else ""
                if len(secret) < 32 or secret.startswith("replace-with"):
                    raise ValueError("Production JWT_SECRET_KEY must be a strong, non-template secret.")
            elif not self.jwt_public_key or not self.jwt_private_key:
                raise ValueError("Asymmetric JWT keys are required for the selected production algorithm.")
        return self


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    return Settings()
