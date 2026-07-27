from __future__ import annotations

import json
import logging
import re
from datetime import datetime, timezone
from typing import Any

from ..core.request_context import get_request_context_optional

_SECRET_KEY = re.compile(r"(?i)(api[_-]?key|authorization|password|secret|token|cookie|private[_-]?key)")
_SECRET_VALUE = re.compile(r"(?i)(bearer\s+[A-Za-z0-9._~+/-]+=*|sk-[A-Za-z0-9_-]{16,}|AIza[0-9A-Za-z_-]{20,})")


def redact_value(value: Any) -> Any:
    if isinstance(value, dict):
        return {key: "[REDACTED]" if _SECRET_KEY.search(str(key)) else redact_value(item) for key, item in value.items()}
    if isinstance(value, list):
        return [redact_value(item) for item in value]
    if isinstance(value, tuple):
        return tuple(redact_value(item) for item in value)
    if isinstance(value, str):
        return _SECRET_VALUE.sub("[REDACTED]", value)
    return value


class JsonFormatter(logging.Formatter):
    def format(self, record: logging.LogRecord) -> str:
        context = get_request_context_optional()
        payload: dict[str, Any] = {
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "level": record.levelname,
            "logger": record.name,
            "message": redact_value(record.getMessage()),
        }
        if context:
            payload.update(
                tenant_id=str(context.tenant_id),
                user_id=str(context.user_id),
                role_code=context.role_code,
                request_id=context.request_id,
                correlation_id=context.correlation_id,
            )
        for key in ("event", "duration_ms", "status_code", "path", "method", "job_id", "job_type"):
            if hasattr(record, key):
                payload[key] = redact_value(getattr(record, key))
        if record.exc_info:
            payload["exception"] = self.formatException(record.exc_info)
        return json.dumps(redact_value(payload), default=str, ensure_ascii=False)


def configure_logging(*, level: str = "INFO", json_logs: bool = True) -> None:
    root = logging.getLogger()
    root.setLevel(level.upper())
    handler = logging.StreamHandler()
    handler.setFormatter(JsonFormatter() if json_logs else logging.Formatter("%(asctime)s %(levelname)s %(name)s %(message)s"))
    root.handlers.clear()
    root.addHandler(handler)
