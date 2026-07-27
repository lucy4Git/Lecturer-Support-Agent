from __future__ import annotations

import asyncio
import json
from pathlib import Path

import pytest

from services.api.app.core.hardening import RedisRateLimiter
from services.api.app.core.settings import Settings
from services.api.app.integrations.malware_scanner import DisabledMalwareScanner
from services.api.app.main import app
from services.api.app.observability.logging import redact_value
from services.api.app.observability.metrics import MetricsRegistry
from services.api.app.services.job_queue import ALLOWED_JOB_TYPES, retry_delay_seconds
from services.database.models import Base

ROOT = Path(__file__).resolve().parents[2]


class _FakeRedisClient:
    def __init__(self, responses: list[list[int]]) -> None:
        self.responses = responses

    async def eval(self, *_args):
        return self.responses.pop(0)


class _FakeGateway:
    def __init__(self, responses: list[list[int]]) -> None:
        self.client = _FakeRedisClient(responses)


def test_v23_registers_operational_reliability_tables() -> None:
    tables = set(Base.metadata.tables)
    assert len(tables) >= 104
    assert {
        "operations.background_jobs",
        "operations.background_job_attempts",
        "operations.dead_letter_jobs",
        "operations.scheduled_jobs",
        "operations.backup_runs",
        "operations.restore_drills",
    }.issubset(tables)


def test_retry_backoff_is_bounded_and_deterministic() -> None:
    assert [retry_delay_seconds(item) for item in range(1, 6)] == [5, 10, 20, 40, 80]
    assert retry_delay_seconds(20) == 3600
    with pytest.raises(ValueError):
        retry_delay_seconds(0)


def test_job_type_allowlist_covers_long_running_platform_work() -> None:
    assert {
        "content.ingest_document",
        "content.generate_export",
        "analytics.generate_report",
        "audit.generate_export",
        "external_access.expire",
        "governance.apply_retention",
        "operations.backup",
        "operations.restore_drill",
    }.issubset(ALLOWED_JOB_TYPES)


def test_rate_limiter_returns_remaining_and_rejects_over_limit() -> None:
    limiter = RedisRateLimiter(
        Settings(_env_file=None, rate_limit_enabled=True),
        gateway=_FakeGateway([[1, 60], [3, 55]]),
    )
    first = asyncio.run(limiter.check("one", limit=2, window_seconds=60))
    third = asyncio.run(limiter.check("one", limit=2, window_seconds=60))
    assert first.allowed and first.remaining == 1
    assert not third.allowed and third.remaining == 0 and third.retry_after_seconds == 55


def test_secret_redaction_is_recursive_and_value_aware() -> None:
    value = {
        "authorization": "Bearer abc.def.ghi",
        "nested": {"api_key": "synthetic-secret-value-for-test", "safe": "retained"},
    }
    redacted = redact_value(value)
    assert redacted["authorization"] == "[REDACTED]"
    assert redacted["nested"]["api_key"] == "[REDACTED]"
    assert redacted["nested"]["safe"] == "retained"


def test_metrics_registry_emits_prometheus_text() -> None:
    registry = MetricsRegistry()
    registry.increment("lsa_test_total", labels={"status": "ok"})
    registry.set_gauge("lsa_test_gauge", 3)
    text = registry.render()
    assert 'lsa_test_total{status="ok"} 1.0' in text
    assert "lsa_test_gauge 3" in text


def test_disabled_malware_scanner_is_explicit_not_fabricated() -> None:
    result = asyncio.run(DisabledMalwareScanner().scan_bytes(b"safe", filename="file.txt"))
    assert result.clean
    assert result.status == "disabled"


def test_production_configuration_fails_closed_without_controls() -> None:
    with pytest.raises(ValueError):
        Settings(
            _env_file=None,
            environment="production",
            ai_enable_development_mock=False,
            jwt_secret_key="x" * 40,
            rate_limit_enabled=True,
            rate_limit_fail_closed=False,
            malware_scan_enabled=True,
            malware_scan_fail_closed=True,
            metrics_enabled=False,
        )


def test_v23_operations_routes_and_public_observability_endpoints_exist() -> None:
    paths = {route.path for route in app.routes}
    assert {
        "/health",
        "/ready",
        "/metrics",
        "/api/v1/operations/jobs",
        "/api/v1/operations/summary",
        "/api/v1/operations/dead-letters/{dead_letter_id}/replay",
        "/api/v1/operations/backups",
        "/api/v1/operations/backups/{backup_run_id}/restore-drills",
    }.issubset(paths)
    assert tuple(map(int, app.version.split("."))) >= (2, 3, 0)


def test_v23_permissions_keep_operations_admin_only() -> None:
    catalogue = json.loads((ROOT / "services/database/seeds/role_permissions.json").read_text())
    roles = {item["code"]: set(item["permissions"]) for item in catalogue["roles"]}
    required = {
        "operations.jobs.read",
        "operations.jobs.manage",
        "operations.backups.read",
        "operations.backups.manage",
    }
    assert required.issubset(roles["institution_administrator"])
    for role in ("head_of_department", "lecturer", "external_reviewer"):
        assert not required.intersection(roles[role])


def test_streamed_request_body_is_rejected_after_crossing_limit() -> None:
    from services.api.app.core.hardening import RequestSizeLimitMiddleware

    messages = [
        {"type": "http.request", "body": b"a" * 600_000, "more_body": True},
        {"type": "http.request", "body": b"b" * 600_000, "more_body": False},
    ]
    sent: list[dict] = []

    async def receive():
        return messages.pop(0)

    async def send(message):
        sent.append(message)

    async def consuming_app(_scope, receive_call, send_call):
        while True:
            message = await receive_call()
            if not message.get("more_body", False):
                break
        await send_call({"type": "http.response.start", "status": 200, "headers": []})
        await send_call({"type": "http.response.body", "body": b"ok"})

    middleware = RequestSizeLimitMiddleware(
        consuming_app,
        Settings(_env_file=None, maximum_request_bytes=1_048_576),
    )
    scope = {
        "type": "http",
        "asgi": {"version": "3.0"},
        "http_version": "1.1",
        "method": "POST",
        "scheme": "http",
        "path": "/upload",
        "raw_path": b"/upload",
        "query_string": b"",
        "headers": [],
        "client": ("127.0.0.1", 1234),
        "server": ("test", 80),
    }
    asyncio.run(middleware(scope, receive, send))
    starts = [item for item in sent if item["type"] == "http.response.start"]
    assert starts and starts[0]["status"] == 413
