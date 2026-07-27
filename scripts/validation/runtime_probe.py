from __future__ import annotations

import argparse
import asyncio
import json
import os
import sys
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Awaitable, Callable

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))


def _result(name: str, status: str, detail: str, *, duration_ms: int = 0, metadata: dict[str, Any] | None = None) -> dict[str, Any]:
    return {
        "name": name,
        "status": status,
        "detail": detail,
        "duration_ms": duration_ms,
        "metadata": metadata or {},
    }


def _safe_error(exc: Exception) -> str:
    text = str(exc).replace("\r", " ").replace("\n", " ")
    for value in os.environ.values():
        if value and len(value) >= 12 and value in text:
            text = text.replace(value, "[REDACTED]")
    return text[:500]


async def _timed(name: str, action: Callable[[], Awaitable[tuple[str, dict[str, Any]]]]) -> dict[str, Any]:
    started = time.perf_counter()
    try:
        detail, metadata = await action()
        return _result(name, "passed", detail, duration_ms=int((time.perf_counter() - started) * 1000), metadata=metadata)
    except Exception as exc:  # validation boundary: capture and report, never leak secrets
        return _result(name, "failed", _safe_error(exc), duration_ms=int((time.perf_counter() - started) * 1000))


async def probe_http(name: str, url: str) -> dict[str, Any]:
    import httpx

    async def action() -> tuple[str, dict[str, Any]]:
        async with httpx.AsyncClient(timeout=15, follow_redirects=True) as client:
            response = await client.get(url)
            response.raise_for_status()
            return f"HTTP {response.status_code}", {"content_type": response.headers.get("content-type", "")}

    return await _timed(name, action)


async def probe_postgresql() -> dict[str, Any]:
    async def action() -> tuple[str, dict[str, Any]]:
        from sqlalchemy import create_engine, text

        url = os.environ.get("MIGRATION_DATABASE_URL") or os.environ.get("DATABASE_URL")
        if not url:
            raise RuntimeError("MIGRATION_DATABASE_URL or DATABASE_URL is not configured")
        engine = create_engine(url, pool_pre_ping=True)
        try:
            with engine.connect() as connection:
                row = connection.execute(text("SELECT current_database(), current_user, current_setting('row_security')")).one()
                revision = connection.execute(text("SELECT version_num FROM alembic_version")).scalar_one_or_none()
            return "PostgreSQL accepted a query", {
                "database": row[0], "database_user": row[1], "row_security": row[2], "alembic_revision": revision
            }
        finally:
            engine.dispose()

    return await _timed("postgresql", action)


async def probe_redis() -> dict[str, Any]:
    async def action() -> tuple[str, dict[str, Any]]:
        import redis.asyncio as redis

        client = redis.from_url(os.environ.get("REDIS_URL", "redis://localhost:6379/0"), decode_responses=True)
        try:
            pong = await client.ping()
            if not pong:
                raise RuntimeError("Redis did not return PONG")
            info = await client.info(section="server")
            return "Redis returned PONG", {"redis_version": info.get("redis_version")}
        finally:
            await client.aclose()

    return await _timed("redis", action)


async def probe_minio() -> dict[str, Any]:
    async def action() -> tuple[str, dict[str, Any]]:
        import boto3

        endpoint = os.environ.get("OBJECT_STORAGE_ENDPOINT", "http://localhost:9000")
        bucket = os.environ.get("OBJECT_STORAGE_BUCKET", "lecturer-support-agent")
        client = boto3.client(
            "s3",
            endpoint_url=endpoint,
            region_name=os.environ.get("OBJECT_STORAGE_REGION", "us-east-1"),
            aws_access_key_id=os.environ.get("OBJECT_STORAGE_ACCESS_KEY"),
            aws_secret_access_key=os.environ.get("OBJECT_STORAGE_SECRET_KEY"),
            use_ssl=os.environ.get("OBJECT_STORAGE_SECURE", "false").lower() == "true",
        )
        client.head_bucket(Bucket=bucket)
        versioning = client.get_bucket_versioning(Bucket=bucket).get("Status", "Disabled")
        if versioning != "Enabled":
            raise RuntimeError(f"Object-storage versioning is {versioning}, expected Enabled")
        return "Object-storage bucket exists and versioning is enabled", {"bucket": bucket, "versioning": versioning}

    return await _timed("minio", action)


async def probe_qdrant() -> dict[str, Any]:
    import httpx

    async def action() -> tuple[str, dict[str, Any]]:
        base = os.environ.get("QDRANT_URL", "http://localhost:6333").rstrip("/")
        collection = os.environ.get("QDRANT_COLLECTION", "lecturer_support_documents")
        headers = {}
        if os.environ.get("QDRANT_API_KEY"):
            headers["api-key"] = os.environ["QDRANT_API_KEY"]
        async with httpx.AsyncClient(timeout=15, headers=headers) as client:
            response = await client.get(f"{base}/collections/{collection}")
            response.raise_for_status()
            payload = response.json()
        return "Qdrant collection is reachable", {"collection": collection, "status": payload.get("result", {}).get("status")}

    return await _timed("qdrant", action)


async def probe_ollama(required_models: list[str], generate: bool) -> dict[str, Any]:
    import httpx

    async def action() -> tuple[str, dict[str, Any]]:
        base = os.environ.get("OLLAMA_BASE_URL", "http://localhost:11434").rstrip("/")
        async with httpx.AsyncClient(timeout=120) as client:
            tags = await client.get(f"{base}/api/tags")
            tags.raise_for_status()
            installed = sorted({str(item.get("name")) for item in tags.json().get("models", [])})
            missing = [model for model in required_models if model not in installed]
            if missing:
                raise RuntimeError("Missing required Ollama model(s): " + ", ".join(missing))
            if generate:
                model = os.environ.get("OLLAMA_DEFAULT_MODEL", required_models[0] if required_models else "qwen3:8b")
                response = await client.post(
                    f"{base}/api/chat",
                    json={
                        "model": model,
                        "stream": False,
                        "messages": [{"role": "user", "content": "Reply with exactly READY."}],
                        "options": {"temperature": 0},
                    },
                )
                response.raise_for_status()
                if not str(response.json().get("message", {}).get("content", "")).strip():
                    raise RuntimeError("Ollama returned an empty generation")
        return "Ollama is reachable and required models are installed", {"installed_model_count": len(installed), "required_models": required_models, "generation_tested": generate}

    return await _timed("ollama", action)


async def probe_crossref() -> dict[str, Any]:
    async def action() -> tuple[str, dict[str, Any]]:
        from services.api.app.ai.source_discovery import CrossrefSourceDiscovery
        from services.api.app.core.settings import Settings

        settings = Settings()
        records = await CrossrefSourceDiscovery(settings).discover("constructive alignment higher education", limit=1)
        if not records:
            raise RuntimeError("Crossref returned no source metadata")
        return "Crossref returned genuine metadata", {"source_key": records[0].source_key, "title": records[0].title[:120]}

    return await _timed("crossref", action)


async def probe_cloud_providers() -> list[dict[str, Any]]:
    from services.api.app.ai.contracts import ChatMessage, ChatRole, ProviderRequest
    from services.api.app.ai.providers import AnthropicProvider, DeepSeekProvider, GeminiProvider, OpenAIProvider
    from services.api.app.core.settings import Settings

    settings = Settings()
    providers = [OpenAIProvider(settings), AnthropicProvider(settings), GeminiProvider(settings), DeepSeekProvider(settings)]
    output: list[dict[str, Any]] = []
    for provider in providers:
        if not provider.configured:
            output.append(_result(provider.name, "skipped", "Provider is not configured; no API call was made", metadata={"default_model": provider.default_model}))
            continue

        async def action(p=provider) -> tuple[str, dict[str, Any]]:
            response = await p.generate(ProviderRequest(
                messages=[ChatMessage(role=ChatRole.USER, content="Reply with exactly READY.")],
                system_prompt="This is a synthetic connectivity check. Do not use external tools or sources.",
                model=p.default_model,
                max_output_tokens=16,
                temperature=0,
            ))
            if not response.text.strip():
                raise RuntimeError("Provider returned an empty response")
            return "Synthetic provider request completed", {"model": response.model, "latency_ms": response.latency_ms}

        output.append(await _timed(provider.name, action))
    return output


async def main_async(args: argparse.Namespace) -> int:
    required_models = [item.strip() for item in args.required_ollama_model if item.strip()]
    probes = [
        probe_postgresql(), probe_redis(), probe_minio(), probe_qdrant(),
        probe_ollama(required_models, args.ollama_generation),
    ]
    if not args.skip_application_probes:
        probes.extend([
            probe_http("api_health", args.api_health_url),
            probe_http("api_ready", args.api_ready_url),
            probe_http("web_sign_in", args.web_url),
        ])
    results = list(await asyncio.gather(*probes))
    if args.crossref:
        results.append(await probe_crossref())
    if args.cloud_providers:
        results.extend(await probe_cloud_providers())
    report = {
        "schema_version": "1.0",
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "machine": {"platform": sys.platform, "python": sys.version.split()[0]},
        "results": results,
        "summary": {
            "passed": sum(item["status"] == "passed" for item in results),
            "failed": sum(item["status"] == "failed" for item in results),
            "skipped": sum(item["status"] == "skipped" for item in results),
        },
    }
    output = Path(args.output)
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(report, indent=2), encoding="utf-8")
    print(json.dumps(report["summary"]))
    return 1 if report["summary"]["failed"] else 0


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Probe live Lecturer Support Agent dependencies without printing secrets.")
    parser.add_argument("--output", required=True)
    parser.add_argument("--required-ollama-model", action="append", default=[])
    parser.add_argument("--ollama-generation", action="store_true")
    parser.add_argument("--cloud-providers", action="store_true")
    parser.add_argument("--crossref", action="store_true")
    parser.add_argument("--api-health-url", default="http://localhost:8000/health")
    parser.add_argument("--api-ready-url", default="http://localhost:8000/ready")
    parser.add_argument("--web-url", default="http://localhost:3000/sign-in")
    parser.add_argument("--skip-application-probes", action="store_true")
    return parser.parse_args()


if __name__ == "__main__":
    raise SystemExit(asyncio.run(main_async(parse_args())))
