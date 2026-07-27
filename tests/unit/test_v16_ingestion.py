from __future__ import annotations

from io import BytesIO
from zipfile import ZIP_DEFLATED, ZipFile

import httpx
import pytest

from services.api.app.ingestion.archive import ArchiveInspectionError, SafeZipExpander
from services.api.app.ingestion.chunking import TextChunker
from services.api.app.ingestion.embeddings import DeterministicEmbeddingClient, OllamaEmbeddingClient
from services.api.app.ingestion.parsers import DocumentParserRegistry
from services.api.app.core.settings import Settings
from services.api.app.integrations.qdrant import QdrantGateway, RetrievalScope
from services.api.app.services.document_versioning import is_document_version_transition_allowed
from uuid import UUID


def test_plain_text_extraction_is_normalised() -> None:
    result = DocumentParserRegistry().extract(
        filename="lesson.txt", media_type="text/plain", content=b"Title\r\n\r\nActivity one"
    )
    assert result.status == "extracted"
    assert result.parser_name == "plain_text_v1"
    assert "Activity one" in result.text
    assert "\r" not in result.text
    assert result.word_count == 3


def test_media_requires_transcript_without_inventing_text() -> None:
    result = DocumentParserRegistry().extract(
        filename="lecture.mp4", media_type="video/mp4", content=b"not-real-video"
    )
    assert result.status == "transcript_required"
    assert result.text == ""
    assert result.transcript_required is True


def test_chunker_is_deterministic_and_overlapping() -> None:
    text = "# Introduction\n\n" + ("Sensors collect data. " * 80) + "\n\n# Activity\n\n" + ("Students connect devices. " * 80)
    chunker = TextChunker(target_characters=700, overlap_characters=80)
    first = chunker.chunk(text)
    second = chunker.chunk(text)
    assert len(first) > 1
    assert [item.sha256 for item in first] == [item.sha256 for item in second]
    assert all(item.token_estimate > 0 for item in first)


def _zip(entries: dict[str, bytes]) -> bytes:
    buffer = BytesIO()
    with ZipFile(buffer, "w", ZIP_DEFLATED) as archive:
        for name, content in entries.items():
            archive.writestr(name, content)
    return buffer.getvalue()


def test_safe_zip_expander_preserves_relative_members() -> None:
    members = SafeZipExpander(maximum_entries=5).expand(_zip({"week1/lesson.txt": b"hello"}))
    assert members[0].path == "week1/lesson.txt"
    assert members[0].content == b"hello"


def test_safe_zip_expander_rejects_traversal() -> None:
    with pytest.raises(ArchiveInspectionError):
        SafeZipExpander().expand(_zip({"../secret.txt": b"no"}))


@pytest.mark.asyncio
async def test_deterministic_embedding_shape_is_stable() -> None:
    client = DeterministicEmbeddingClient(dimension=12)
    first = await client.embed(["IoT sensors"])
    second = await client.embed(["IoT sensors"])
    assert first == second
    assert len(first[0]) == 12


@pytest.mark.asyncio
async def test_ollama_embedding_adapter_uses_embed_endpoint() -> None:
    captured = {}
    def handler(request: httpx.Request) -> httpx.Response:
        captured["path"] = request.url.path
        return httpx.Response(200, json={"embeddings": [[0.0] * 8]})
    settings = Settings(_env_file=None, embedding_dimension=8, ollama_embedding_model="embed-test")
    async with httpx.AsyncClient(transport=httpx.MockTransport(handler), base_url="http://ollama") as http:
        client = OllamaEmbeddingClient(settings, http)
        vectors = await client.embed(["content"])
    assert captured["path"] == "/api/embed"
    assert len(vectors[0]) == 8


@pytest.mark.asyncio
async def test_qdrant_search_sends_named_vector_and_tenant_filter() -> None:
    captured = {}
    def handler(request: httpx.Request) -> httpx.Response:
        captured["json"] = __import__("json").loads(request.content)
        return httpx.Response(200, json={"result": []})
    settings = Settings(_env_file=None, qdrant_collection="test")
    async with httpx.AsyncClient(transport=httpx.MockTransport(handler), base_url="http://qdrant") as http:
        gateway = QdrantGateway(settings, http)
        await gateway.search(
            vector=[0.1] * 8,
            scope=RetrievalScope(
                tenant_id=UUID("11111111-1111-1111-1111-111111111111"),
                user_id=UUID("22222222-2222-2222-2222-222222222222"),
                include_public=False,
            ),
        )
    assert captured["json"]["vector"]["name"] == "default"
    assert captured["json"]["filter"]["must"][0]["key"] == "tenant_id"


def test_document_version_transition_graph_is_controlled() -> None:
    assert is_document_version_transition_allowed("working", "under_review")
    assert is_document_version_transition_allowed("under_review", "approved")
    assert not is_document_version_transition_allowed("working", "published")
    assert not is_document_version_transition_allowed("archived", "working")
