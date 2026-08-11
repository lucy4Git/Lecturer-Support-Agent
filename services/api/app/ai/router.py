from __future__ import annotations

from collections.abc import AsyncIterator
from dataclasses import dataclass

from ..core.settings import Settings
from .contracts import PrivacyClass, ProviderAttempt, ProviderRequest, ProviderResponse
from .providers import (
    AIProvider,
    AnthropicProvider,
    DeepSeekProvider,
    DevelopmentMockProvider,
    GeminiProvider,
    OllamaProvider,
    OpenAIProvider,
    ProviderError,
)


@dataclass(slots=True)
class RoutedResponse:
    response: ProviderResponse
    attempts: list[ProviderAttempt]
    routing_reason: str


class ModelRouter:
    def __init__(self, settings: Settings, providers: dict[str, AIProvider] | None = None) -> None:
        self.settings = settings
        self.providers = providers or {
            "openai": OpenAIProvider(settings),
            "anthropic": AnthropicProvider(settings),
            "google_gemini": GeminiProvider(settings),
            "deepseek": DeepSeekProvider(settings),
            "ollama": OllamaProvider(settings),
        }
        if settings.ai_enable_development_mock and settings.environment.lower() != "production":
            self.providers["development_mock"] = DevelopmentMockProvider()

    def candidate_names(
        self,
        privacy: PrivacyClass,
        *,
        allowed_providers: set[str] | None = None,
        denied_providers: set[str] | None = None,
    ) -> list[str]:
        configured_order = [name.strip() for name in self.settings.ai_fallback_order.split(",") if name.strip()]
        if self.settings.ai_default_provider != "auto":
            configured_order = [self.settings.ai_default_provider, *configured_order]
        if self.settings.ai_require_local_for_restricted and privacy in {
            PrivacyClass.CONFIDENTIAL,
            PrivacyClass.RESTRICTED_ASSESSMENT,
        }:
            configured_order = ["ollama"]
        deduplicated = list(dict.fromkeys(configured_order))
        if "development_mock" in self.providers:
            deduplicated.append("development_mock")
        if allowed_providers:
            deduplicated = [name for name in deduplicated if name in allowed_providers]
        if denied_providers:
            deduplicated = [name for name in deduplicated if name not in denied_providers]
        return deduplicated

    async def generate(
        self,
        request: ProviderRequest,
        *,
        privacy: PrivacyClass,
        allowed_providers: set[str] | None = None,
        denied_providers: set[str] | None = None,
    ) -> RoutedResponse:
        attempts: list[ProviderAttempt] = []
        candidates = self.candidate_names(
            privacy,
            allowed_providers=allowed_providers,
            denied_providers=denied_providers,
        )
        for provider_name in candidates:
            provider = self.providers.get(provider_name)
            if provider is None:
                attempts.append(ProviderAttempt(provider=provider_name, model="", status="skipped", reason="provider_not_registered"))
                continue
            if not provider.configured:
                attempts.append(ProviderAttempt(provider=provider_name, model=provider.default_model, status="skipped", reason="provider_not_configured"))
                continue
            try:
                response = await provider.generate(request.model_copy(update={"model": request.model or provider.default_model}))
                attempts.append(
                    ProviderAttempt(
                        provider=provider.name,
                        model=response.model,
                        status="completed",
                        reason="selected_by_capability_privacy_fallback_policy",
                        latency_ms=response.latency_ms,
                    )
                )
                return RoutedResponse(
                    response=response,
                    attempts=attempts,
                    routing_reason=(
                        "restricted_data_local_route" if privacy in {PrivacyClass.CONFIDENTIAL, PrivacyClass.RESTRICTED_ASSESSMENT}
                        and self.settings.ai_require_local_for_restricted else "capability_privacy_fallback_route"
                    ),
                )
            except ProviderError as exc:
                attempts.append(
                    ProviderAttempt(
                        provider=provider.name,
                        model=provider.default_model,
                        status="failed",
                        reason=str(exc),
                        error_code=exc.code,
                    )
                )
        raise ProviderError("router", "No configured AI provider completed the request.", code="all_providers_failed")

    async def stream(
        self,
        request: ProviderRequest,
        *,
        privacy: PrivacyClass,
        allowed_providers: set[str] | None = None,
        denied_providers: set[str] | None = None,
    ) -> AsyncIterator[str]:
        """Yield text tokens from the first available provider, falling back if needed."""
        candidates = self.candidate_names(
            privacy,
            allowed_providers=allowed_providers,
            denied_providers=denied_providers,
        )
        for provider_name in candidates:
            provider = self.providers.get(provider_name)
            if provider is None or not provider.configured:
                continue
            try:
                req = request.model_copy(update={"model": request.model or provider.default_model})
                async for token in provider.generate_stream(req):
                    yield token
                return
            except ProviderError:
                continue
        raise ProviderError("router", "No configured AI provider completed the stream request.", code="all_providers_failed")

    def status(self) -> list[dict[str, str | bool]]:
        return [
            {
                "provider": name,
                "configured": provider.configured,
                "default_model": provider.default_model,
            }
            for name, provider in self.providers.items()
        ]
