"""Validate hosted deployment configuration without disclosing secret values."""
from __future__ import annotations

from urllib.parse import parse_qs, urlsplit

from services.api.app.core.settings import get_settings


def _database_summary(name: str, value: str, expected_user: str | None) -> dict[str, object]:
    normalised = value.replace("postgresql+psycopg://", "postgresql://", 1)
    parsed = urlsplit(normalised)
    if parsed.scheme not in {"postgres", "postgresql"} or not parsed.hostname:
        raise SystemExit(f"{name} is not a valid PostgreSQL URL.")
    if expected_user and parsed.username != expected_user:
        raise SystemExit(f"{name} must authenticate as {expected_user}, not the migration owner.")
    query = parse_qs(parsed.query)
    ssl_mode = (query.get("sslmode") or [""])[0]
    if ssl_mode not in {"require", "verify-ca", "verify-full"}:
        raise SystemExit(f"{name} must require TLS using sslmode=require/verify-ca/verify-full.")
    return {
        "configured": True,
        "host_is_local": parsed.hostname in {"localhost", "127.0.0.1"},
        "tls_mode": ssl_mode,
        "role": parsed.username,
        "pooled": "pooler" in parsed.hostname.lower(),
    }


def main() -> None:
    settings = get_settings()
    environment = settings.environment.lower()
    hosted = environment in {"staging", "production"}
    urls = {
        "DATABASE_URL": _database_summary(
            "DATABASE_URL", settings.database_url.get_secret_value(), "lsa_app" if hosted else None
        ),
        "AUTH_DATABASE_URL": _database_summary(
            "AUTH_DATABASE_URL", settings.auth_database_url.get_secret_value(), "lsa_auth" if hosted else None
        ),
        "WORKER_DATABASE_URL": _database_summary(
            "WORKER_DATABASE_URL", settings.worker_database_url.get_secret_value(), "lsa_worker" if hosted else None
        ),
        "MIGRATION_DATABASE_URL": _database_summary(
            "MIGRATION_DATABASE_URL", settings.migration_database_url.get_secret_value(), None
        ),
    }
    if hosted and urls["MIGRATION_DATABASE_URL"]["pooled"]:
        raise SystemExit("MIGRATION_DATABASE_URL must use Neon's direct endpoint, not the pooled endpoint.")
    if hosted and any(summary["host_is_local"] for summary in urls.values()):
        raise SystemExit("Hosted deployment database URLs cannot point to localhost.")
    if hosted and not settings.public_app_url.startswith("https://"):
        raise SystemExit("PUBLIC_APP_URL must use HTTPS in staging and production.")
    if hosted and (not settings.object_storage_secure or not settings.object_storage_endpoint.startswith("https://")):
        raise SystemExit("Hosted object storage must use HTTPS with OBJECT_STORAGE_SECURE=true.")
    if settings.email_delivery_enabled:
        if settings.smtp_host in {"localhost", "127.0.0.1"}:
            raise SystemExit("Hosted email delivery cannot use a localhost SMTP host.")
        if not settings.smtp_password:
            raise SystemExit("EMAIL_DELIVERY_ENABLED requires SMTP_PASSWORD.")
    if environment == "production" and settings.enable_demo_seed:
        raise SystemExit("Production demonstration seeding is prohibited.")

    # Output only non-secret readiness facts.
    print(f"Deployment configuration valid for {environment}.")
    for name, summary in urls.items():
        print(
            f"{name}: configured={summary['configured']} role={summary['role']} "
            f"tls={summary['tls_mode']} pooled={summary['pooled']}"
        )
    print(
        "Providers: "
        f"gemini={bool(settings.google_gemini_api_key)} "
        f"openai={bool(settings.openai_api_key)} "
        f"anthropic={bool(settings.anthropic_api_key)} "
        f"deepseek={bool(settings.deepseek_api_key)}"
    )
    print(
        f"Object storage: secure={settings.object_storage_secure} "
        f"versioning_mode={settings.object_storage_versioning_mode}"
    )


if __name__ == "__main__":
    main()
