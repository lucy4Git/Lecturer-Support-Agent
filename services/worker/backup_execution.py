from __future__ import annotations

import asyncio
import base64
import hashlib
import json
import shutil
from dataclasses import dataclass
from datetime import date, datetime, time, timezone
from decimal import Decimal
from pathlib import Path
from typing import Any
from uuid import UUID

import httpx
from sqlalchemy import select, text
from sqlalchemy.ext.asyncio import AsyncSession

from services.api.app.core.settings import Settings, get_settings
from services.api.app.integrations.object_storage import S3ObjectStorage
from services.database.models import Base


@dataclass(frozen=True, slots=True)
class BackupComponentResult:
    component: str
    status: str
    files: int = 0
    bytes_written: int = 0
    details: dict[str, Any] | None = None


def _sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


class BackupExecutor:
    """Create tenant-scoped backups without placing secrets in command lines.

    The executor writes only to the configured backup root, which is ignored by
    Git. PostgreSQL credentials are passed to ``pg_dump`` via environment
    variables. Object storage is exported only beneath the tenant prefix, and
    Qdrant points are exported with a mandatory tenant filter.
    """

    def __init__(self, settings: Settings | None = None) -> None:
        self.settings = settings or get_settings()
        self.root = Path(self.settings.backup_root_path).expanduser().resolve()

    def run_directory(self, *, tenant_id: UUID, run_id: UUID, attempt: int = 1) -> Path:
        destination = self.root / str(tenant_id) / str(run_id) / f"attempt-{max(attempt, 1):03d}"
        destination.mkdir(parents=True, exist_ok=False)
        return destination

    async def execute(
        self,
        *,
        tenant_id: UUID,
        run_id: UUID,
        session: AsyncSession,
        include_database: bool,
        include_object_storage: bool,
        include_vector_store: bool,
        attempt: int = 1,
    ) -> tuple[Path, dict[str, Any], str]:
        destination = self.run_directory(tenant_id=tenant_id, run_id=run_id, attempt=attempt)
        results: dict[str, Any] = {}
        try:
            if include_database:
                results["postgresql"] = (await self.backup_postgresql(session, destination, tenant_id)).__dict__
            if include_object_storage:
                results["object_storage"] = (
                    await self.backup_object_storage(destination, tenant_id)
                ).__dict__
            if include_vector_store:
                results["qdrant"] = (await self.backup_qdrant(destination, tenant_id)).__dict__

            manifest = self._write_manifest(
                destination=destination,
                tenant_id=tenant_id,
                run_id=run_id,
                component_results=results,
            )
            return destination, results, _sha256_file(manifest)
        except Exception:
            # Keep partial evidence for diagnosis; never report it as completed.
            partial = destination / "PARTIAL_BACKUP.json"
            partial.write_text(
                json.dumps({"created_at": _utc_now(), "component_results": results}, indent=2),
                encoding="utf-8",
            )
            raise

    async def backup_postgresql(
        self, session: AsyncSession, destination: Path, tenant_id: UUID
    ) -> BackupComponentResult:
        """Export only rows visible to the active tenant-scoped worker session.

        This is a tenant portability/restore package, not a whole-platform
        ``pg_dump``. Platform disaster-recovery backups remain controlled by
        the operator scripts under ``scripts/operations``.
        """

        relational_root = destination / "postgresql-tenant-export"
        relational_root.mkdir(parents=True, exist_ok=True)
        table_index: list[dict[str, Any]] = []
        total_rows = 0
        total_bytes = 0

        def encode(value: Any) -> Any:
            if value is None or isinstance(value, (str, int, float, bool)):
                return value
            if isinstance(value, bytes):
                return {"encoding": "base64", "value": base64.b64encode(value).decode("ascii")}
            if isinstance(value, (datetime, date, time)):
                return value.isoformat()
            if isinstance(value, UUID):
                return str(value)
            if isinstance(value, Decimal):
                return str(value)
            if isinstance(value, dict):
                return {str(key): encode(item) for key, item in value.items()}
            if isinstance(value, (list, tuple, set)):
                return [encode(item) for item in value]
            return str(value)

        for table in Base.metadata.sorted_tables:
            if "tenant_id" not in table.c:
                continue
            rows = (await session.execute(select(table).where(table.c.tenant_id == tenant_id))).mappings().all()
            path = relational_root / f"{table.schema}.{table.name}.jsonl"
            with path.open("w", encoding="utf-8", newline="\n") as handle:
                for row in rows:
                    handle.write(json.dumps({key: encode(value) for key, value in row.items()}, sort_keys=True) + "\n")
            count = len(rows)
            size = path.stat().st_size
            total_rows += count
            total_bytes += size
            table_index.append({
                "table": f"{table.schema}.{table.name}", "rows": count,
                "file": path.name, "sha256": _sha256_file(path),
            })

        for view_name in ("tenant.current_institution", "iam.current_tenant_users"):
            rows = (await session.execute(text(f"SELECT * FROM {view_name}"))).mappings().all()
            path = relational_root / f"{view_name}.jsonl"
            with path.open("w", encoding="utf-8", newline="\n") as handle:
                for row in rows:
                    handle.write(json.dumps({key: encode(value) for key, value in row.items()}, sort_keys=True) + "\n")
            total_rows += len(rows)
            total_bytes += path.stat().st_size
            table_index.append({
                "table": view_name, "rows": len(rows), "file": path.name,
                "sha256": _sha256_file(path),
            })

        index = relational_root / "tables.json"
        index.write_text(json.dumps(table_index, indent=2, sort_keys=True), encoding="utf-8")
        return BackupComponentResult(
            component="postgresql", status="completed",
            files=sum(1 for item in table_index if item.get("file")),
            bytes_written=total_bytes + index.stat().st_size,
            details={
                "scope": "tenant_rows_only", "rows": total_rows,
                "index": str(index.relative_to(destination)), "index_sha256": _sha256_file(index),
            },
        )

    async def backup_object_storage(
        self, destination: Path, tenant_id: UUID
    ) -> BackupComponentResult:
        storage = S3ObjectStorage(self.settings)
        object_root = destination / "object-storage"
        object_root.mkdir(parents=True, exist_ok=True)
        prefix = f"tenants/{tenant_id}/"

        def _export() -> tuple[list[dict[str, Any]], int]:
            paginator = storage.client.get_paginator("list_object_versions")
            records: list[dict[str, Any]] = []
            total = 0
            for page in paginator.paginate(Bucket=storage.bucket, Prefix=prefix):
                for item in page.get("Versions", []):
                    key = str(item["Key"])
                    version_id = str(item.get("VersionId") or "null")
                    token = hashlib.sha256(f"{key}:{version_id}".encode()).hexdigest()
                    target = object_root / f"{token}.bin"
                    with target.open("wb") as handle:
                        kwargs: dict[str, Any] = {
                            "Bucket": storage.bucket,
                            "Key": key,
                            "VersionId": version_id,
                        }
                        response = storage.client.get_object(**kwargs)
                        body = response["Body"]
                        for chunk in iter(lambda: body.read(1024 * 1024), b""):
                            handle.write(chunk)
                    size = target.stat().st_size
                    total += size
                    records.append(
                        {
                            "key": key,
                            "version_id": version_id,
                            "is_latest": bool(item.get("IsLatest")),
                            "last_modified": item.get("LastModified").isoformat()
                            if item.get("LastModified")
                            else None,
                            "etag": str(item.get("ETag") or "").strip('"'),
                            "size": size,
                            "backup_file": target.name,
                            "sha256": _sha256_file(target),
                        }
                    )
                for marker in page.get("DeleteMarkers", []):
                    records.append(
                        {
                            "key": str(marker["Key"]),
                            "version_id": str(marker.get("VersionId") or "null"),
                            "delete_marker": True,
                            "is_latest": bool(marker.get("IsLatest")),
                        }
                    )
            return records, total

        records, total = await asyncio.to_thread(_export)
        index = object_root / "versions.json"
        index.write_text(json.dumps(records, indent=2, sort_keys=True), encoding="utf-8")
        return BackupComponentResult(
            component="object_storage",
            status="completed",
            files=sum(1 for record in records if not record.get("delete_marker")),
            bytes_written=total,
            details={
                "tenant_prefix": prefix,
                "index": str(index.relative_to(destination)),
                "index_sha256": _sha256_file(index),
            },
        )

    async def backup_qdrant(self, destination: Path, tenant_id: UUID) -> BackupComponentResult:
        headers: dict[str, str] = {}
        if self.settings.qdrant_api_key:
            headers["api-key"] = self.settings.qdrant_api_key.get_secret_value()
        output = destination / "qdrant-points.jsonl"
        offset: Any = None
        count = 0
        bytes_written = 0
        async with httpx.AsyncClient(
            base_url=self.settings.qdrant_url,
            headers=headers,
            timeout=self.settings.backup_component_timeout_seconds,
        ) as client:
            with output.open("wb") as handle:
                while True:
                    body: dict[str, Any] = {
                        "filter": {
                            "must": [
                                {"key": "tenant_id", "match": {"value": str(tenant_id)}}
                            ]
                        },
                        "limit": 256,
                        "with_payload": True,
                        "with_vector": True,
                    }
                    if offset is not None:
                        body["offset"] = offset
                    response = await client.post(
                        f"/collections/{self.settings.qdrant_collection}/points/scroll",
                        json=body,
                    )
                    if response.status_code == 404:
                        output.unlink(missing_ok=True)
                        return BackupComponentResult(
                            component="qdrant",
                            status="collection_not_found",
                            details={"collection": self.settings.qdrant_collection},
                        )
                    response.raise_for_status()
                    result = response.json().get("result", {})
                    points = result.get("points", [])
                    for point in points:
                        line = (json.dumps(point, sort_keys=True) + "\n").encode("utf-8")
                        handle.write(line)
                        bytes_written += len(line)
                        count += 1
                    offset = result.get("next_page_offset")
                    if offset is None or not points:
                        break
        return BackupComponentResult(
            component="qdrant",
            status="completed",
            files=1,
            bytes_written=bytes_written,
            details={
                "filename": output.name,
                "points": count,
                "sha256": _sha256_file(output),
            },
        )

    def _write_manifest(
        self,
        *,
        destination: Path,
        tenant_id: UUID,
        run_id: UUID,
        component_results: dict[str, Any],
    ) -> Path:
        files = []
        for path in sorted(destination.rglob("*")):
            if path.is_file() and path.name not in {"backup-manifest.json", "backup-manifest.sha256"}:
                files.append(
                    {
                        "path": path.relative_to(destination).as_posix(),
                        "size_bytes": path.stat().st_size,
                        "sha256": _sha256_file(path),
                    }
                )
        manifest = {
            "format_version": "2.5",
            "created_at": _utc_now(),
            "tenant_id": str(tenant_id),
            "backup_run_id": str(run_id),
            "storage_encryption_attested": self.settings.backup_storage_encryption_attested,
            "component_results": component_results,
            "files": files,
        }
        path = destination / "backup-manifest.json"
        path.write_text(json.dumps(manifest, indent=2, sort_keys=True), encoding="utf-8")
        (destination / "backup-manifest.sha256").write_text(_sha256_file(path) + "\n", encoding="utf-8")
        return path


class RestoreDrillExecutor:
    """Validate backup integrity and restore tooling without touching production data.

    A full isolated restore can be delegated to an institution-approved command.
    Without that command, the drill verifies every file and asks ``pg_restore``
    to parse the PostgreSQL archive catalogue. The result is explicitly labelled
    as a catalogue drill rather than a completed data restoration.
    """

    def __init__(self, settings: Settings | None = None) -> None:
        self.settings = settings or get_settings()

    async def execute(self, backup_directory: Path, isolated_environment: str) -> dict[str, Any]:
        manifest_path = backup_directory / "backup-manifest.json"
        if not manifest_path.exists():
            raise RuntimeError("backup-manifest.json is missing")
        manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
        verified = 0
        for item in manifest.get("files", []):
            path = backup_directory / item["path"]
            if not path.exists() or _sha256_file(path) != item["sha256"]:
                raise RuntimeError(f"Backup component failed integrity validation: {item['path']}")
            verified += 1

        database_catalogue_entries: int | None = None
        tenant_index = backup_directory / "postgresql-tenant-export" / "tables.json"
        tenant_rows: int | None = None
        if tenant_index.exists():
            entries = json.loads(tenant_index.read_text(encoding="utf-8"))
            tenant_rows = sum(int(item.get("rows") or 0) for item in entries)
            for item in entries:
                if item.get("file"):
                    exported = tenant_index.parent / item["file"]
                    if not exported.exists() or _sha256_file(exported) != item["sha256"]:
                        raise RuntimeError(f"Tenant relational export failed validation: {item.get('table')}")
        database_dump = backup_directory / "postgresql.dump"
        if database_dump.exists():
            executable = shutil.which(self.settings.pg_restore_executable)
            if executable is None:
                raise RuntimeError(f"{self.settings.pg_restore_executable} is not available on PATH")
            process = await asyncio.create_subprocess_exec(
                executable,
                "--list",
                str(database_dump),
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
            )
            stdout, stderr = await process.communicate()
            if process.returncode != 0:
                raise RuntimeError(f"pg_restore catalogue check failed: {stderr.decode(errors='replace')[:2000]}")
            database_catalogue_entries = sum(
                1 for line in stdout.decode(errors="replace").splitlines() if line and not line.startswith(";")
            )

        external_result: dict[str, Any] | None = None
        if self.settings.restore_drill_executable:
            executable = shutil.which(self.settings.restore_drill_executable) or self.settings.restore_drill_executable
            process = await asyncio.create_subprocess_exec(
                executable,
                str(backup_directory),
                isolated_environment,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
            )
            stdout, stderr = await process.communicate()
            if process.returncode != 0:
                raise RuntimeError(f"Approved restore drill failed: {stderr.decode(errors='replace')[:2000]}")
            external_result = {"status": "completed", "output": stdout.decode(errors="replace")[-4000:]}

        return {
            "status": "isolated_restore_completed" if external_result else "manifest_and_catalogue_validated",
            "isolated_environment": isolated_environment,
            "files_verified": verified,
            "database_catalogue_entries": database_catalogue_entries,
            "tenant_relational_rows": tenant_rows,
            "external_restore": external_result,
            "limitation": None if external_result else "No approved isolated restore executable was configured.",
        }
