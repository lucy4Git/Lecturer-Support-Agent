from __future__ import annotations

import stat
from dataclasses import dataclass
from io import BytesIO
from pathlib import PurePosixPath
from zipfile import BadZipFile, ZipFile


class ArchiveInspectionError(ValueError):
    pass


@dataclass(frozen=True, slots=True)
class ArchiveMember:
    path: str
    content: bytes
    size_bytes: int


class SafeZipExpander:
    """Inspect and expand ZIP files without trusting archive paths or sizes."""

    def __init__(
        self,
        *,
        maximum_entries: int = 500,
        maximum_total_uncompressed_bytes: int = 2_147_483_648,
        maximum_member_bytes: int = 1_073_741_824,
        allow_nested_archives: bool = False,
    ) -> None:
        self.maximum_entries = maximum_entries
        self.maximum_total_uncompressed_bytes = maximum_total_uncompressed_bytes
        self.maximum_member_bytes = maximum_member_bytes
        self.allow_nested_archives = allow_nested_archives

    def expand(self, content: bytes) -> list[ArchiveMember]:
        try:
            archive = ZipFile(BytesIO(content))
        except BadZipFile as exc:
            raise ArchiveInspectionError("The uploaded ZIP archive is invalid.") from exc
        with archive:
            entries = [item for item in archive.infolist() if not item.is_dir()]
            if len(entries) > self.maximum_entries:
                raise ArchiveInspectionError("The ZIP archive contains too many files.")
            total = sum(item.file_size for item in entries)
            if total > self.maximum_total_uncompressed_bytes:
                raise ArchiveInspectionError("The ZIP archive expands beyond the permitted size.")
            members: list[ArchiveMember] = []
            for item in entries:
                path = PurePosixPath(item.filename.replace("\\", "/"))
                if path.is_absolute() or ".." in path.parts:
                    raise ArchiveInspectionError("The ZIP archive contains an unsafe path.")
                mode = item.external_attr >> 16
                if mode and stat.S_ISLNK(mode):
                    raise ArchiveInspectionError("Symbolic links are not permitted in ZIP uploads.")
                if item.flag_bits & 0x1:
                    raise ArchiveInspectionError("Encrypted ZIP members are not supported.")
                if item.file_size > self.maximum_member_bytes:
                    raise ArchiveInspectionError(f"Archive member {path.name} is too large.")
                if not self.allow_nested_archives and path.suffix.lower() in {".zip", ".7z", ".rar", ".tar", ".gz"}:
                    raise ArchiveInspectionError("Nested archives are disabled for safe bulk ingestion.")
                data = archive.read(item)
                if len(data) != item.file_size:
                    raise ArchiveInspectionError(f"Archive member {path.name} could not be read safely.")
                members.append(ArchiveMember(path=str(path), content=data, size_bytes=len(data)))
            return members
