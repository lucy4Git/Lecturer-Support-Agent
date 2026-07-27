from __future__ import annotations

from ..contracts import ProviderRequest, ProviderResponse
from .base import AIProvider


class DevelopmentMockProvider(AIProvider):
    name = "development_mock"
    default_model = "deterministic-teaching-mock-1"
    configured = True

    async def generate(self, request: ProviderRequest) -> ProviderResponse:
        user_request = request.messages[-1].content if request.messages else "Teaching request"
        return ProviderResponse(
            provider=self.name,
            model=self.default_model,
            text=(
                "# Draft teaching support output\n\n"
                f"**Request:** {user_request}\n\n"
                "## Purpose\nThis deterministic development response confirms that the unified conversation "
                "pipeline, routing, persistence contract, and inline output interface are connected.\n\n"
                "## Implementation note\nConfigure Ollama or a cloud provider in the local `.env` file to generate the full "
                "teaching output. This mock does not fabricate sources or claim institutional approval.\n\n"
                "> Human review is required before formal teaching or assessment use."
            ),
            finish_reason="mock_completed",
            latency_ms=1,
        )
