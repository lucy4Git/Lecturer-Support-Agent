from __future__ import annotations

import json

import httpx
import pytest

from services.api.app.ai.contracts import (
    ChatMessage,
    ChatRole,
    PrivacyClass,
    ProviderRequest,
    ProviderResponse,
    SourceCandidate,
    TeachingTaskType,
)
from services.api.app.ai.integrity import CitationIntegrityGuard
from services.api.app.ai.prompt_builder import PromptBuilder
from services.api.app.ai.providers.base import AIProvider, ProviderError
from services.api.app.ai.providers.gemini import GeminiProvider
from services.api.app.ai.providers.ollama import OllamaProvider
from services.api.app.ai.router import ModelRouter
from services.api.app.ai.source_discovery import CrossrefSourceDiscovery
from services.api.app.ai.task_classifier import TeachingTaskClassifier
from services.api.app.core.settings import Settings


class FakeProvider(AIProvider):
    def __init__(self, name: str, *, configured: bool = True, fail: bool = False) -> None:
        self.name = name
        self._configured = configured
        self._fail = fail

    @property
    def configured(self) -> bool:
        return self._configured

    @property
    def default_model(self) -> str:
        return f"{self.name}-model"

    async def generate(self, request: ProviderRequest) -> ProviderResponse:
        if self._fail:
            raise ProviderError(self.name, "simulated failure", code="simulated")
        return ProviderResponse(provider=self.name, model=request.model, text="# Completed")


def request() -> ProviderRequest:
    return ProviderRequest(
        messages=[ChatMessage(role=ChatRole.USER, content="Create a lesson plan")],
        system_prompt="system",
        model="",
        max_output_tokens=1000,
        temperature=0.2,
    )


def test_classifier_detects_practical_lesson_and_context() -> None:
    result = TeachingTaskClassifier().classify(
        "Generate a 2-hour practical lesson on IoT sensors for diploma students using the attached module guide.",
        has_attachments=True,
    )
    assert result.task_type == TeachingTaskType.PRACTICAL_LESSON
    assert result.detected_entities["duration"] == "2 hour"
    assert result.detected_entities["academic_level"] == "diploma"
    assert result.institutional_context_required is True


def test_classifier_requires_human_review_for_examination() -> None:
    result = TeachingTaskClassifier().classify("Create a 100-mark final examination.")
    assert result.task_type == TeachingTaskType.EXAMINATION
    assert result.human_review_required is True
    assert result.detected_entities["total_marks"] == 100


def test_classifier_marks_restricted_assessment_as_local_only() -> None:
    result = TeachingTaskClassifier().classify("Review this confidential exam and moderation report.")
    assert result.privacy_classification == PrivacyClass.RESTRICTED_ASSESSMENT


def test_integrity_guard_keeps_only_retrieved_source_markers() -> None:
    source = SourceCandidate(
        source_key="source-one",
        source_type="journal-article",
        title="Verified source",
        canonical_url="https://doi.org/10.1000/example",
        doi="10.1000/example",
        retrieved_by="test",
        retrieval_query="test",
    )
    text = "Supported [S1]. Invented [S9]. https://fake.example 10.9999/fake"
    result = CitationIntegrityGuard().validate(text, [source])
    assert "[S1]" in result.text
    assert "[unverified citation removed]" in result.text
    assert "[unverified link removed]" in result.text
    assert "[unverified DOI removed]" in result.text
    assert result.cited_source_keys == ["source-one"]
    assert result.removed_unverified_references == 3


def test_prompt_builder_does_not_create_sources_when_pack_empty() -> None:
    classification = TeachingTaskClassifier().classify("Explain formative assessment.")
    prompt = PromptBuilder().build_system_prompt(
        classification=classification,
        user_role="lecturer",
        sources=[],
    )
    assert "VERIFIED SOURCE PACK\n(none)" in prompt
    assert "Never create a reference list entry" in prompt


@pytest.mark.asyncio
async def test_router_falls_back_after_provider_failure() -> None:
    settings = Settings(
        _env_file=None,
        ai_fallback_order="first,second",
        ai_enable_development_mock=False,
        ai_require_local_for_restricted=False,
    )
    router = ModelRouter(
        settings,
        providers={
            "first": FakeProvider("first", fail=True),
            "second": FakeProvider("second"),
        },
    )
    result = await router.generate(request(), privacy=PrivacyClass.INTERNAL)
    assert result.response.provider == "second"
    assert [attempt.status for attempt in result.attempts] == ["failed", "completed"]


@pytest.mark.asyncio
async def test_router_restricts_confidential_requests_to_ollama() -> None:
    settings = Settings(
        _env_file=None,
        ai_fallback_order="openai,ollama",
        ai_enable_development_mock=False,
        ai_require_local_for_restricted=True,
    )
    router = ModelRouter(
        settings,
        providers={
            "openai": FakeProvider("openai"),
            "ollama": FakeProvider("ollama"),
        },
    )
    result = await router.generate(request(), privacy=PrivacyClass.CONFIDENTIAL)
    assert result.response.provider == "ollama"
    assert result.routing_reason == "restricted_data_local_route"


@pytest.mark.asyncio
async def test_ollama_adapter_uses_chat_endpoint_and_parses_usage() -> None:
    captured: dict = {}

    def handler(incoming: httpx.Request) -> httpx.Response:
        captured["url"] = str(incoming.url)
        captured["body"] = json.loads(incoming.content)
        return httpx.Response(
            200,
            json={
                "model": "qwen3:8b",
                "message": {"role": "assistant", "content": "Generated lesson"},
                "done": True,
                "done_reason": "stop",
                "prompt_eval_count": 10,
                "eval_count": 20,
            },
        )

    settings = Settings(_env_file=None, ollama_default_model="qwen3:8b")
    async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as client:
        response = await OllamaProvider(settings, client).generate(request().model_copy(update={"model": "qwen3:8b"}))
    assert captured["url"].endswith("/api/chat")
    assert captured["body"]["stream"] is False
    assert response.text == "Generated lesson"
    assert response.input_tokens == 10
    assert response.output_tokens == 20


@pytest.mark.asyncio
async def test_gemini_adapter_parses_grounding_metadata() -> None:
    def handler(_: httpx.Request) -> httpx.Response:
        return httpx.Response(
            200,
            json={
                "candidates": [
                    {
                        "content": {"parts": [{"text": "Grounded answer [S1]"}]},
                        "finishReason": "STOP",
                        "groundingMetadata": {
                            "groundingChunks": [
                                {"web": {"uri": "https://example.edu/source", "title": "Example source"}}
                            ]
                        },
                    }
                ],
                "usageMetadata": {"promptTokenCount": 4, "candidatesTokenCount": 8},
            },
        )

    settings = Settings(
        _env_file=None,
        google_gemini_api_key="test-key",
        google_gemini_default_model="gemini-test",
    )
    async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as client:
        response = await GeminiProvider(settings, client).generate(request().model_copy(update={"model": "gemini-test"}))
    assert response.text == "Grounded answer [S1]"
    assert response.provider_sources[0].title == "Example source"
    assert response.provider_sources[0].retrieved_by == "gemini_grounding_metadata"


@pytest.mark.asyncio
async def test_crossref_connector_returns_only_real_metadata_records() -> None:
    def handler(incoming: httpx.Request) -> httpx.Response:
        assert incoming.url.path.endswith("/works")
        return httpx.Response(
            200,
            json={
                "message": {
                    "items": [
                        {
                            "DOI": "10.1000/valid",
                            "title": ["Valid teaching study"],
                            "author": [{"given": "Ada", "family": "Scholar"}],
                            "publisher": "Academic Publisher",
                            "published-online": {"date-parts": [[2025, 6, 1]]},
                            "URL": "https://doi.org/10.1000/valid",
                            "type": "journal-article",
                            "score": 42.0,
                        },
                        {"title": []},
                    ]
                }
            },
        )

    settings = Settings(_env_file=None, crossref_contact_email="team@example.org")
    async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as client:
        rows = await CrossrefSourceDiscovery(settings, client).discover("active learning")
    assert len(rows) == 1
    assert rows[0].doi == "10.1000/valid"
    assert rows[0].authors == ["Ada Scholar"]
    assert rows[0].metadata["recorded_from_actual_retrieval"] is True
