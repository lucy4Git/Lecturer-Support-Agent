from __future__ import annotations

import asyncio
import json
from collections.abc import AsyncIterator

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

    async def list_models(self) -> list[tuple[str, str]]:
        """Query the local Ollama server's /api/tags — a free, local, no-billing
        call — for the models actually pulled and runnable. Falls back to just the
        configured default model if the server is unreachable."""
        if not self.configured:
            return []
        try:
            async with httpx.AsyncClient(timeout=3.0) as client:
                response = await client.get(f"{self.settings.ollama_base_url.rstrip('/')}/api/tags")
                response.raise_for_status()
                payload = response.json()
        except (httpx.HTTPError, ValueError):
            return [(self.default_model, self.default_model)]
        models: list[tuple[str, str]] = []
        for entry in payload.get("models", []):
            name = str(entry.get("name") or "")
            capabilities = entry.get("capabilities") or []
            if not name or "completion" not in capabilities:
                continue
            models.append((name, name))
        return models or [(self.default_model, self.default_model)]

    def _body(self, request: ProviderRequest, *, stream: bool) -> dict:
        body: dict = {
            "model": request.model or self.default_model,
            "messages": [
                {"role": "system", "content": request.system_prompt},
                *[{"role": m.role.value, "content": m.content} for m in request.messages],
            ],
            "stream": stream,
            "options": {
                "temperature": request.temperature,
                "num_predict": request.max_output_tokens,
            },
        }
        if request.structured_schema:
            body["format"] = request.structured_schema
        return body

    async def generate_stream(self, request: ProviderRequest) -> AsyncIterator[str]:  # type: ignore[override]
        if not self.configured:
            raise ProviderError(self.name, "Ollama is not configured.", code="not_configured")
        url = f"{self.settings.ollama_base_url.rstrip('/')}/api/chat"
        timeout = self.settings.ai_request_timeout_seconds
        try:
            async with asyncio.timeout(timeout):
                async with httpx.AsyncClient(timeout=timeout) as client:
                    async with client.stream("POST", url, headers={"Content-Type": "application/json"}, json=self._body(request, stream=True)) as response:
                        if response.status_code >= 400:
                            await response.aread()
                            raise ProviderError(self.name, f"Ollama stream error {response.status_code}", code="stream_error")
                        async for line in response.aiter_lines():
                            line = line.strip()
                            if not line:
                                continue
                            try:
                                event = json.loads(line)
                            except json.JSONDecodeError:
                                continue
                            chunk = event.get("message", {}).get("content", "")
                            if chunk:
                                yield chunk
                            if event.get("done"):
                                break
        except (TimeoutError, asyncio.TimeoutError, httpx.TimeoutException) as exc:
            raise ProviderError(self.name, "Ollama generation timed out.", code="timeout") from exc

    async def generate(self, request: ProviderRequest) -> ProviderResponse:
        if not self.configured:
            raise ProviderError(self.name, "Ollama is not configured.", code="not_configured")
        body = self._body(request, stream=False)
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
