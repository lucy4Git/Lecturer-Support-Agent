from __future__ import annotations

import json
from collections.abc import AsyncIterator
from urllib.parse import quote

import httpx

from ...core.settings import Settings
from ..contracts import ProviderRequest, ProviderResponse, SourceCandidate
from .base import AIProvider, ProviderError
from .http_utils import post_json


class GeminiProvider(AIProvider):
    name = "google_gemini"

    def __init__(self, settings: Settings, client: httpx.AsyncClient | None = None) -> None:
        self.settings = settings
        self.client = client

    @property
    def configured(self) -> bool:
        return bool(self.settings.google_gemini_api_key and self.settings.google_gemini_api_key.get_secret_value().strip() and self.default_model)

    @property
    def default_model(self) -> str:
        return self.settings.google_gemini_default_model.strip()

    def _body(self, request: ProviderRequest) -> dict:
        return {
            "systemInstruction": {"parts": [{"text": request.system_prompt}]},
            "contents": [
                {
                    "role": "model" if message.role.value == "assistant" else "user",
                    "parts": [{"text": message.content}],
                }
                for message in request.messages
                if message.role.value in {"user", "assistant"}
            ],
            "generationConfig": {
                "temperature": request.temperature,
                "maxOutputTokens": request.max_output_tokens,
            },
        }

    async def generate_stream(self, request: ProviderRequest) -> AsyncIterator[str]:  # type: ignore[override]
        if not self.configured:
            raise ProviderError(self.name, "Gemini is not configured.", code="not_configured")
        model = request.model or self.default_model
        url = (
            f"{self.settings.google_gemini_base_url.rstrip('/')}/v1beta/models/"
            f"{quote(model, safe='')}:streamGenerateContent?alt=sse"
        )
        headers = {
            "x-goog-api-key": self.settings.google_gemini_api_key.get_secret_value(),
            "Content-Type": "application/json",
        }
        async with httpx.AsyncClient(timeout=self.settings.ai_request_timeout_seconds) as client:
            async with client.stream("POST", url, headers=headers, json=self._body(request)) as response:
                if response.status_code >= 400:
                    await response.aread()
                    raise ProviderError(self.name, f"Gemini stream error {response.status_code}", code="stream_error")
                async for line in response.aiter_lines():
                    if not line.startswith("data: "):
                        continue
                    raw = line[6:].strip()
                    if not raw:
                        continue
                    try:
                        event = json.loads(raw)
                    except json.JSONDecodeError:
                        continue
                    candidates = event.get("candidates") or []
                    candidate = candidates[0] if candidates else {}
                    for part in candidate.get("content", {}).get("parts") or []:
                        chunk = part.get("text", "")
                        if chunk:
                            yield chunk

    async def generate(self, request: ProviderRequest) -> ProviderResponse:
        if not self.configured:
            raise ProviderError(self.name, "Gemini is not configured.", code="not_configured")
        model = request.model or self.default_model
        body = self._body(request)
        payload, latency, headers = await post_json(
            provider=self.name,
            url=(
                f"{self.settings.google_gemini_base_url.rstrip('/')}/v1beta/models/"
                f"{quote(model, safe='')}:generateContent"
            ),
            headers={
                "x-goog-api-key": self.settings.google_gemini_api_key.get_secret_value(),
                "Content-Type": "application/json",
            },
            body=body,
            timeout_seconds=self.settings.ai_request_timeout_seconds,
            client=self.client,
        )
        candidates = payload.get("candidates") or []
        candidate = candidates[0] if candidates else {}
        text = "\n".join(
            str(part.get("text")) for part in candidate.get("content", {}).get("parts") or []
            if part.get("text")
        )
        if not text:
            raise ProviderError(self.name, "Gemini returned no text.", code="empty_response")
        usage = payload.get("usageMetadata") or {}
        return ProviderResponse(
            provider=self.name,
            model=model,
            text=text,
            input_tokens=usage.get("promptTokenCount"),
            output_tokens=usage.get("candidatesTokenCount"),
            finish_reason=candidate.get("finishReason"),
            latency_ms=latency,
            request_id=headers.get("x-request-id"),
            provider_sources=self._grounding_sources(candidate, request.messages[-1].content),
        )

    @staticmethod
    def _grounding_sources(candidate: dict, query: str) -> list[SourceCandidate]:
        chunks = candidate.get("groundingMetadata", {}).get("groundingChunks") or []
        sources: list[SourceCandidate] = []
        for index, chunk in enumerate(chunks, start=1):
            web = chunk.get("web") or {}
            uri, title = web.get("uri"), web.get("title")
            if uri and title:
                sources.append(
                    SourceCandidate(
                        source_key=f"gemini-grounding-{index}",
                        source_type="web",
                        title=str(title),
                        canonical_url=str(uri),
                        retrieved_by="gemini_grounding_metadata",
                        retrieval_query=query,
                        rank=index,
                        reliability_tier="provider_grounding_metadata",
                    )
                )
        return sources
