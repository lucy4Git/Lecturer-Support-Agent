from __future__ import annotations

import httpx

from ...core.settings import Settings
from ..contracts import ProviderRequest, ProviderResponse
from .base import AIProvider, ProviderError
from .http_utils import post_json


class AnthropicProvider(AIProvider):
    name = "anthropic"

    def __init__(self, settings: Settings, client: httpx.AsyncClient | None = None) -> None:
        self.settings = settings
        self.client = client

    @property
    def configured(self) -> bool:
        return bool(self.settings.anthropic_api_key and self.settings.anthropic_api_key.get_secret_value().strip() and self.default_model)

    @property
    def default_model(self) -> str:
        return self.settings.anthropic_default_model.strip()

    async def generate(self, request: ProviderRequest) -> ProviderResponse:
        if not self.configured:
            raise ProviderError(self.name, "Anthropic is not configured.", code="not_configured")
        body = {
            "model": request.model or self.default_model,
            "max_tokens": request.max_output_tokens,
            "temperature": request.temperature,
            "system": request.system_prompt,
            "messages": [
                {"role": m.role.value, "content": m.content}
                for m in request.messages
                if m.role.value in {"user", "assistant"}
            ],
        }
        payload, latency, headers = await post_json(
            provider=self.name,
            url=f"{self.settings.anthropic_base_url.rstrip('/')}/v1/messages",
            headers={
                "x-api-key": self.settings.anthropic_api_key.get_secret_value(),
                "anthropic-version": self.settings.anthropic_api_version,
                "Content-Type": "application/json",
            },
            body=body,
            timeout_seconds=self.settings.ai_request_timeout_seconds,
            client=self.client,
        )
        text = "\n".join(
            str(block.get("text")) for block in payload.get("content") or []
            if block.get("type") == "text" and block.get("text")
        )
        if not text:
            raise ProviderError(self.name, "Anthropic returned no text.", code="empty_response")
        usage = payload.get("usage") or {}
        return ProviderResponse(
            provider=self.name,
            model=str(payload.get("model") or body["model"]),
            text=text,
            input_tokens=usage.get("input_tokens"),
            output_tokens=usage.get("output_tokens"),
            finish_reason=payload.get("stop_reason"),
            latency_ms=latency,
            request_id=headers.get("request-id") or payload.get("id"),
        )
