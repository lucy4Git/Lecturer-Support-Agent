"""Idempotent pre-deploy gate for Render/Neon/S3/Qdrant."""
from __future__ import annotations

import asyncio
import os
import subprocess
import sys

from services.api.app.core.settings import get_settings
from services.api.app.integrations.object_storage import S3ObjectStorage
from services.api.app.integrations.qdrant import QdrantGateway


def run(command: list[str]) -> None:
    subprocess.run(command, check=True)


async def ensure_external_services() -> None:
    settings = get_settings()
    storage = S3ObjectStorage(settings)
    await storage.ensure_bucket()
    ready, versioning = await storage.probe_bucket()
    if not ready:
        raise RuntimeError(f"Object storage versioning is not ready: {versioning}")
    qdrant = QdrantGateway(settings)
    try:
        await qdrant.ensure_collection(vector_size=settings.embedding_dimension)
    finally:
        await qdrant.close()


def main() -> None:
    # Validate all hosted contracts without printing any secret values.
    run([sys.executable, "scripts/deployment/validate_deployment_configuration.py"])
    # Create NOLOGIN placeholder roles before Alembic so row_level_security.sql
    # can reference lsa_app, lsa_auth and lsa_worker without UndefinedObject errors.
    run([sys.executable, "scripts/deployment/ensure_database_roles.py"])
    # The same migration chain runs in local, staging, and production.
    run([sys.executable, "-m", "alembic", "upgrade", "head"])
    # Convert placeholder roles to LOGIN roles using the environment passwords.
    run([sys.executable, "scripts/deployment/bootstrap_database_roles.py"])
    asyncio.run(ensure_external_services())

    environment = os.getenv("ENVIRONMENT", "development").lower()
    seed_enabled = os.getenv("ENABLE_DEMO_SEED", "false").lower() in {"1", "true", "yes", "on"}
    if seed_enabled:
        if environment == "production":
            raise RuntimeError("Production refuses demonstration seed execution.")
        run([sys.executable, "-m", "services.database.seeds.seed_foundation"])
    print(f"Pre-deploy gate completed for {environment}.")


if __name__ == "__main__":
    main()
