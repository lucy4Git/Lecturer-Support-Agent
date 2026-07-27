from __future__ import annotations

import httpx

from ...core.settings import Settings
from ..contracts import ProviderRequest, ProviderResponse
from .base import AIProvider, ProviderError
from .http_utils import post_json


class DeepSeekProvider(AIProvider):
    name = "deepseek"

    def __init__(self, settings: Settings, client: httpx.AsyncClient | None = None) -> None:
        self.settings = settings
        self.client = client

    @property
    def configured(self) -> bool:
        return bool(self.settings.deepseek_api_key and self.settings.deepseek_api_key.get_secret_value().strip() and self.default_model)

    @property
    def default_model(self) -> str:
        return self.settings.deepseek_default_model.strip()

    async def generate(self, request: ProviderRequest) -> ProviderResponse:
        if not self.configured:
            raise ProviderError(self.name, "DeepSeek is not configured.", code="not_configured")
        body = {
            "model": request.model or self.default_model,
            "messages": [
                {"role": "system", "content": request.system_prompt},
                *[{"role": m.role.value, "content": m.content} for m in request.messages],
            ],
            "max_tokens": request.max_output_tokens,
            "temperature": request.temperature,
            "stream": False,
        }
        payload, latency, headers = await post_json(
            provider=self.name,
            url=f"{self.settings.deepseek_base_url.rstrip('/')}/chat/completions",
            headers={
                "Authorization": f"Bearer {self.settings.deepseek_api_key.get_secret_value()}",
                "Content-Type": "application/json",
            },
            body=body,
            timeout_seconds=self.settings.ai_request_timeout_seconds,
            client=self.client,
        )
        choices = payload.get("choices") or []
        choice = choices[0] if choices else {}
        text = str(choice.get("message", {}).get("content") or "")
        if not text:
            raise ProviderError(self.name, "DeepSeek returned no text.", code="empty_response")
        usage = payload.get("usage") or {}
        return ProviderResponse(
            provider=self.name,
            model=str(payload.get("model") or body["model"]),
            text=text,
            input_tokens=usage.get("prompt_tokens"),
            output_tokens=usage.get("completion_tokens"),
            finish_reason=choice.get("finish_reason"),
            latency_ms=latency,
            request_id=headers.get("x-request-id") or payload.get("id"),
        )
