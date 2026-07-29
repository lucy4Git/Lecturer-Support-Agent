from __future__ import annotations

from uuid import uuid4

import pytest

from services.api.app.main import app
from services.api.app.services.job_queue import ALLOWED_JOB_TYPES
from services.database.models import Base, NotificationDelivery, RetentionRun, RetentionRunItem
from services.worker.handlers import HANDLERS, _uuid


def test_v24_tables_are_registered() -> None:
    assert len(Base.metadata.tables) >= 107
    assert NotificationDelivery.__table__.fullname == "governance.notification_deliveries"
    assert RetentionRun.__table__.fullname == "privacy.retention_runs"
    assert RetentionRunItem.__table__.fullname == "privacy.retention_run_items"


def test_all_allowlisted_domain_jobs_have_handlers() -> None:
    assert ALLOWED_JOB_TYPES == set(HANDLERS)


def test_uuid_parser_accepts_uuid_text() -> None:
    value = uuid4()
    assert _uuid(str(value), "id") == value


def test_uuid_parser_rejects_opaque_invalid_text() -> None:
    with pytest.raises(ValueError, match="must be a valid UUID"):
        _uuid("not-a-uuid", "document_version_id")


def test_v24_operations_routes_are_registered() -> None:
    paths = set(app.openapi()["paths"].keys())
    assert {
        "/api/v1/operations/schedules",
        "/api/v1/operations/schedules/{schedule_id}",
        "/api/v1/operations/notification-deliveries",
        "/api/v1/operations/retention-runs",
    } <= paths


def test_backup_handlers_are_connected_by_v25() -> None:
    assert HANDLERS["operations.backup"].__name__ == "backup_handler"
    assert HANDLERS["operations.restore_drill"].__name__ == "restore_drill_handler"


def test_domain_handlers_are_no_longer_placeholders() -> None:
    for job_type in ALLOWED_JOB_TYPES:
        assert HANDLERS[job_type].__name__ != "owner_machine_handler_required"


def test_v24_openapi_exposes_retention_as_async_request() -> None:
    schema = app.openapi()
    operation = schema["paths"]["/api/v1/operations/retention-runs"]["post"]
    assert "202" in operation["responses"]
