from __future__ import annotations

import csv
import io
import os
from abc import ABC, abstractmethod
from dataclasses import dataclass
from typing import Any

import httpx

from ..core.outbound_url import validate_outbound_url
from ..core.settings import Settings, get_settings


@dataclass(frozen=True, slots=True)
class IntegrationTestResult:
    ok: bool
    adapter: str
    detail: str
    capabilities: list[str]


class AcademicSystemAdapter(ABC):
    def __init__(self, *, base_url: str, secret_reference: str | None, configuration: dict, settings: Settings | None = None) -> None:
        self.settings = settings or get_settings()
        if base_url and base_url != "local":
            validate_outbound_url(base_url, self.settings, purpose="Academic integration base URL")
        self.base_url = base_url.rstrip("/")
        self.secret_reference = secret_reference
        self.configuration = configuration

    def _secret(self) -> str:
        if not self.secret_reference:
            raise RuntimeError("The integration has no secret reference.")
        value = os.getenv(self.secret_reference)
        if not value:
            raise RuntimeError(f"The secret reference {self.secret_reference} is not configured.")
        return value

    @abstractmethod
    async def test_connection(self) -> IntegrationTestResult: ...

    @abstractmethod
    async def pull(self, sync_type: str, *, cursor: str | None = None, limit: int = 1000) -> tuple[list[dict[str, Any]], str | None]: ...


class CanvasAdapter(AcademicSystemAdapter):
    async def _get(self, path: str, params: dict | None = None) -> httpx.Response:
        async with httpx.AsyncClient(timeout=self.settings.integration_http_timeout_seconds, follow_redirects=False) as client:
            return await client.get(
                f"{self.base_url}/api/v1/{path.lstrip('/')}",
                params=params,
                headers={"Authorization": f"Bearer {self._secret()}", "Accept": "application/json+canvas-string-ids"},
            )

    async def test_connection(self) -> IntegrationTestResult:
        response = await self._get("users/self/profile")
        return IntegrationTestResult(response.is_success, "canvas", f"HTTP {response.status_code}", ["courses", "users", "enrolments", "assignments"])

    async def pull(self, sync_type: str, *, cursor: str | None = None, limit: int = 1000) -> tuple[list[dict[str, Any]], str | None]:
        paths = {"courses": "courses", "users": "accounts/self/users", "enrolments": "accounts/self/enrollments"}
        if sync_type not in paths:
            raise ValueError(f"Canvas sync type is not supported: {sync_type}")
        response = await self._get(paths[sync_type], {"per_page": min(limit, 100), "page": cursor or "1"})
        response.raise_for_status()
        return list(response.json()), None


class MoodleAdapter(AcademicSystemAdapter):
    async def _call(self, function: str, params: dict | None = None) -> Any:
        payload = {
            "wstoken": self._secret(),
            "wsfunction": function,
            "moodlewsrestformat": "json",
            **(params or {}),
        }
        async with httpx.AsyncClient(timeout=self.settings.integration_http_timeout_seconds) as client:
            response = await client.post(f"{self.base_url}/webservice/rest/server.php", data=payload)
        response.raise_for_status()
        data = response.json()
        if isinstance(data, dict) and data.get("exception"):
            raise RuntimeError(str(data.get("message") or data["exception"]))
        return data

    async def test_connection(self) -> IntegrationTestResult:
        data = await self._call("core_webservice_get_site_info")
        return IntegrationTestResult(bool(data.get("sitename")), "moodle", str(data.get("sitename") or "connected"), ["courses", "users", "enrolments"])

    async def pull(self, sync_type: str, *, cursor: str | None = None, limit: int = 1000) -> tuple[list[dict[str, Any]], str | None]:
        functions = {"courses": "core_course_get_courses", "users": "core_user_get_users"}
        if sync_type == "courses":
            data = await self._call(functions[sync_type])
            return list(data)[:limit], None
        if sync_type == "users":
            data = await self._call(functions[sync_type], {"criteria[0][key]": "email", "criteria[0][value]": "%"})
            return list(data.get("users") or [])[:limit], None
        raise ValueError(f"Moodle sync type is not supported: {sync_type}")


class OneRosterCSVAdapter(AcademicSystemAdapter):
    """Parse institution-provided OneRoster 1.2 CSV data without vendor lock-in."""

    async def test_connection(self) -> IntegrationTestResult:
        return IntegrationTestResult(True, "oneroster_csv", "CSV package validation is available.", ["orgs", "users", "courses", "classes", "enrolments"])

    async def pull(self, sync_type: str, *, cursor: str | None = None, limit: int = 1000) -> tuple[list[dict[str, Any]], str | None]:
        content = self.configuration.get("csv_content", {}).get(sync_type)
        if not isinstance(content, str):
            raise ValueError(f"No OneRoster CSV content was supplied for {sync_type}.")
        rows = list(csv.DictReader(io.StringIO(content)))
        return rows[:limit], None


class OneRosterRESTAdapter(AcademicSystemAdapter):
    """OneRoster 1.2 REST consumer for approved institutional providers."""

    async def _get(self, resource: str, *, offset: int = 0, limit: int = 100) -> httpx.Response:
        headers = {"Authorization": f"Bearer {self._secret()}", "Accept": "application/json"}
        async with httpx.AsyncClient(timeout=self.settings.integration_http_timeout_seconds, follow_redirects=False) as client:
            return await client.get(
                f"{self.base_url}/ims/oneroster/rostering/v1p2/{resource}",
                headers=headers, params={"offset": offset, "limit": min(limit, 10000)},
            )

    async def test_connection(self) -> IntegrationTestResult:
        response = await self._get("orgs", limit=1)
        return IntegrationTestResult(response.is_success, "oneroster_rest", f"HTTP {response.status_code}", ["orgs", "users", "courses", "classes", "enrollments"])

    async def pull(self, sync_type: str, *, cursor: str | None = None, limit: int = 1000) -> tuple[list[dict[str, Any]], str | None]:
        resources = {"orgs": "orgs", "users": "users", "courses": "courses", "classes": "classes", "enrolments": "enrollments", "enrollments": "enrollments"}
        resource = resources.get(sync_type)
        if resource is None:
            raise ValueError(f"OneRoster REST sync type is not supported: {sync_type}")
        offset = int(cursor or 0)
        response = await self._get(resource, offset=offset, limit=limit)
        response.raise_for_status()
        payload = response.json()
        key = resource
        rows = list(payload.get(key) or []) if isinstance(payload, dict) else []
        next_cursor = str(offset + len(rows)) if len(rows) >= min(limit, 10000) else None
        return rows, next_cursor


class GenericRESTAdapter(AcademicSystemAdapter):
    """Config-driven, read-only JSON adapter. Canonical writes remain staged."""

    async def test_connection(self) -> IntegrationTestResult:
        path = str(self.configuration.get("health_path") or "/")
        async with httpx.AsyncClient(timeout=self.settings.integration_http_timeout_seconds, follow_redirects=False) as client:
            response = await client.get(f"{self.base_url}{path}", headers=self._headers())
        return IntegrationTestResult(response.is_success, "generic_rest", f"HTTP {response.status_code}", sorted((self.configuration.get("endpoints") or {}).keys()))

    async def pull(self, sync_type: str, *, cursor: str | None = None, limit: int = 1000) -> tuple[list[dict[str, Any]], str | None]:
        endpoint = (self.configuration.get("endpoints") or {}).get(sync_type)
        if not isinstance(endpoint, str):
            raise ValueError(f"Generic REST sync type is not configured: {sync_type}")
        params = {"limit": limit}
        if cursor:
            params[str(self.configuration.get("cursor_parameter") or "cursor")] = cursor
        async with httpx.AsyncClient(timeout=self.settings.integration_http_timeout_seconds, follow_redirects=False) as client:
            response = await client.get(f"{self.base_url}{endpoint}", headers=self._headers(), params=params)
        response.raise_for_status()
        payload = response.json()
        records_path = str(self.configuration.get("records_field") or "records")
        rows = payload.get(records_path) if isinstance(payload, dict) else payload
        if not isinstance(rows, list):
            raise ValueError("Generic REST response did not contain a list of records.")
        next_cursor = payload.get(str(self.configuration.get("next_cursor_field") or "next_cursor")) if isinstance(payload, dict) else None
        return [row for row in rows[:limit] if isinstance(row, dict)], str(next_cursor) if next_cursor else None

    def _headers(self) -> dict[str, str]:
        headers = {"Accept": "application/json"}
        if self.secret_reference:
            scheme = str(self.configuration.get("auth_scheme") or "Bearer")
            headers["Authorization"] = f"{scheme} {self._secret()}"
        return headers


def build_academic_adapter(*, integration_type: str, base_url: str | None, secret_reference: str | None, configuration: dict, settings: Settings | None = None) -> AcademicSystemAdapter:
    if integration_type == "canvas":
        return CanvasAdapter(base_url=base_url or "", secret_reference=secret_reference, configuration=configuration, settings=settings)
    if integration_type == "moodle":
        return MoodleAdapter(base_url=base_url or "", secret_reference=secret_reference, configuration=configuration, settings=settings)
    if integration_type == "oneroster_csv":
        return OneRosterCSVAdapter(base_url=base_url or "local", secret_reference=secret_reference, configuration=configuration, settings=settings)
    if integration_type == "oneroster_rest":
        return OneRosterRESTAdapter(base_url=base_url or "", secret_reference=secret_reference, configuration=configuration, settings=settings)
    if integration_type == "generic_rest":
        return GenericRESTAdapter(base_url=base_url or "", secret_reference=secret_reference, configuration=configuration, settings=settings)
    raise ValueError(f"Unsupported academic integration type: {integration_type}")
