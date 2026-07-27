from __future__ import annotations

import httpx

from ...core.settings import Settings
from ..contracts import ProviderRequest, ProviderResponse
from .base import AIProvider, ProviderError
from .http_utils import post_json


class OpenAIProvider(AIProvider):
    name = "openai"

    def __init__(self, settings: Settings, client: httpx.AsyncClient | None = None) -> None:
        self.settings = settings
        self.client = client

    @property
    def configured(self) -> bool:
        return bool(self.settings.openai_api_key and self.settings.openai_api_key.get_secret_value().strip() and self.default_model)

    @property
    def default_model(self) -> str:
        return self.settings.openai_default_model.strip()

    async def generate(self, request: ProviderRequest) -> ProviderResponse:
        if not self.configured:
            raise ProviderError(self.name, "OpenAI is not configured.", code="not_configured")
        input_messages = [
            {"role": message.role.value, "content": message.content}
            for message in request.messages
            if message.role.value != "system"
        ]
        body = {
            "model": request.model or self.default_model,
            "instructions": request.system_prompt,
            "input": input_messages,
            "max_output_tokens": request.max_output_tokens,
            "temperature": request.temperature,
            "store": False,
        }
        payload, latency, headers = await post_json(
            provider=self.name,
            url=f"{self.settings.openai_base_url.rstrip('/')}/responses",
            headers={
                "Authorization": f"Bearer {self.settings.openai_api_key.get_secret_value()}",
                "Content-Type": "application/json",
            },
            body=body,
            timeout_seconds=self.settings.ai_request_timeout_seconds,
            client=self.client,
        )
        text = payload.get("output_text") or self._extract_text(payload)
        if not text:
            raise ProviderError(self.name, "OpenAI returned no text.", code="empty_response")
        usage = payload.get("usage") or {}
        return ProviderResponse(
            provider=self.name,
            model=str(payload.get("model") or body["model"]),
            text=text,
            input_tokens=usage.get("input_tokens"),
            output_tokens=usage.get("output_tokens"),
            finish_reason=payload.get("status"),
            latency_ms=latency,
            request_id=headers.get("x-request-id") or payload.get("id"),
        )

    @staticmethod
    def _extract_text(payload: dict) -> str:
        parts: list[str] = []
        for output in payload.get("output") or []:
            for content in output.get("content") or []:
                if content.get("type") in {"output_text", "text"} and content.get("text"):
                    parts.append(str(content["text"]))
        return "\n".join(parts)
