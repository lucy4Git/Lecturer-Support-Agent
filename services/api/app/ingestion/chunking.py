from __future__ import annotations

import hashlib
import re
from dataclasses import dataclass


@dataclass(frozen=True, slots=True)
class ChunkDraft:
    index: int
    text: str
    sha256: str
    character_start: int
    character_end: int
    token_estimate: int
    section_title: str | None = None


class TextChunker:
    """Deterministic paragraph-aware chunking with bounded overlap."""

    def __init__(self, *, target_characters: int = 3200, overlap_characters: int = 320) -> None:
        if target_characters < 400:
            raise ValueError("target_characters must be at least 400")
        if overlap_characters < 0 or overlap_characters >= target_characters:
            raise ValueError("overlap_characters must be non-negative and smaller than target")
        self.target_characters = target_characters
        self.overlap_characters = overlap_characters

    def chunk(self, text: str) -> list[ChunkDraft]:
        normalised = re.sub(r"\r\n?", "\n", text).strip()
        if not normalised:
            return []
        paragraphs = [part.strip() for part in re.split(r"\n{2,}", normalised) if part.strip()]
        chunks: list[ChunkDraft] = []
        current = ""
        current_start = 0
        search_from = 0
        section: str | None = None

        def emit(value: str, start: int, title: str | None) -> None:
            value = value.strip()
            if not value:
                return
            end = start + len(value)
            chunks.append(
                ChunkDraft(
                    index=len(chunks),
                    text=value,
                    sha256=hashlib.sha256(value.encode("utf-8")).hexdigest(),
                    character_start=start,
                    character_end=end,
                    token_estimate=max(1, (len(value) + 3) // 4),
                    section_title=title,
                )
            )

        for paragraph in paragraphs:
            if re.match(r"^(#{1,6}\s+|[A-Z][A-Z0-9 &:/-]{4,80}$)", paragraph):
                section = paragraph.lstrip("# ").strip()[:500]
            paragraph_start = normalised.find(paragraph, search_from)
            if paragraph_start < 0:
                paragraph_start = search_from
            search_from = paragraph_start + len(paragraph)
            candidate = f"{current}\n\n{paragraph}".strip() if current else paragraph
            if current and len(candidate) > self.target_characters:
                emit(current, current_start, section)
                overlap = current[-self.overlap_characters :].lstrip() if self.overlap_characters else ""
                current = f"{overlap}\n\n{paragraph}".strip() if overlap else paragraph
                current_start = max(0, paragraph_start - len(overlap))
            else:
                if not current:
                    current_start = paragraph_start
                current = candidate
        emit(current, current_start, section)
        return chunks
