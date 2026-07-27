from __future__ import annotations

import httpx

from ...core.settings import Settings
from ..contracts import ProviderRequest, ProviderResponse
from .base import AIProvider, ProviderError
from .http_utils import post_json


class OllamaProvider(AIProvider):
    name = "ollama"

    def __init__(self, settings: Settings, client: httpx.AsyncClient | None = None) -> None:
        self.settings = settings
        self.client = client

    @property
    def configured(self) -> bool:
        return bool(self.default_model and self.settings.ollama_base_url)

    @property
    def default_model(self) -> str:
        return self.settings.ollama_default_model.strip()

    async def generate(self, request: ProviderRequest) -> ProviderResponse:
        if not self.configured:
            raise ProviderError(self.name, "Ollama is not configured.", code="not_configured")
        body = {
            "model": request.model or self.default_model,
            "messages": [
                {"role": "system", "content": request.system_prompt},
                *[{"role": m.role.value, "content": m.content} for m in request.messages],
            ],
            "stream": False,
            "options": {
                "temperature": request.temperature,
                "num_predict": request.max_output_tokens,
            },
        }
        if request.structured_schema:
            body["format"] = request.structured_schema
        payload, latency, _ = await post_json(
            provider=self.name,
            url=f"{self.settings.ollama_base_url.rstrip('/')}/api/chat",
            headers={"Content-Type": "application/json"},
            body=body,
            timeout_seconds=self.settings.ai_request_timeout_seconds,
            client=self.client,
        )
        text = str(payload.get("message", {}).get("content") or "")
        if not text:
            raise ProviderError(self.name, "Ollama returned no text.", code="empty_response")
        return ProviderResponse(
            provider=self.name,
            model=str(payload.get("model") or body["model"]),
            text=text,
            input_tokens=payload.get("prompt_eval_count"),
            output_tokens=payload.get("eval_count"),
            finish_reason=payload.get("done_reason"),
            latency_ms=latency,
            raw_metadata={
                "total_duration_ns": payload.get("total_duration"),
                "load_duration_ns": payload.get("load_duration"),
            },
        )
