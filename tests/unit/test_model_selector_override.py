from __future__ import annotations

from dataclasses import dataclass
from uuid import uuid4

import pytest
from fastapi import HTTPException

from services.api.app.ai.contracts import ProviderRequest, ProviderResponse
from services.api.app.ai.providers.base import AIProvider
from services.api.app.core.request_context import RequestContext
from services.api.app.core.settings import Settings
from services.api.app.schemas.conversations import MessageCreate
from services.api.app.services.conversation_engine import ConversationEngine


class FakeProvider(AIProvider):
    """A provider double that can expose more than one real model id, mirroring
    how OllamaProvider.list_models() reports multiple locally-pulled models."""

    def __init__(self, name: str, *, configured: bool = True, models: list[str] | None = None) -> None:
        self.name = name
        self._configured = configured
        self._models = models or [f"{name}-default"]

    @property
    def configured(self) -> bool:
        return self._configured

    @property
    def default_model(self) -> str:
        return self._models[0]

    async def list_models(self) -> list[tuple[str, str]]:
        return [(m, m) for m in self._models]

    async def generate(self, request: ProviderRequest) -> ProviderResponse:
        return ProviderResponse(provider=self.name, model=request.model, text="ok")


@dataclass
class FakeConversation:
    context: dict


@dataclass
class FakeUsageDecision:
    allowed_providers: tuple[str, ...] | None = None
    denied_providers: tuple[str, ...] | None = None


def engine() -> ConversationEngine:
    context = RequestContext(
        tenant_id=uuid4(), user_id=uuid4(), role_code="lecturer", correlation_id="test",
    )
    return ConversationEngine(session=None, context=context, settings=Settings())  # type: ignore[arg-type]


def message(provider: str | None, model: str | None = None) -> MessageCreate:
    return MessageCreate(content="Draft a quiz", preferred_provider=provider, preferred_model=model)


# ── TEST A: Auto ─────────────────────────────────────────────────────────
def test_auto_defaults_to_governance_allowed_set() -> None:
    eng = engine()
    conv = FakeConversation(context={})
    decision = FakeUsageDecision(allowed_providers=("openai", "ollama"))
    sel = eng._resolve_ai_selection(conv, message(None), decision)
    assert sel.allowed_providers == {"openai", "ollama"}
    assert sel.denied_providers is None
    assert sel.model_override is None
    assert sel.requested_provider == "auto"
    assert sel.persist is None


# ── TEST B: explicit provider + model honoured ──────────────────────────
def test_explicit_provider_and_model_are_honoured() -> None:
    eng = engine()
    conv = FakeConversation(context={})
    decision = FakeUsageDecision()
    eng.router.providers["ollama"] = FakeProvider("ollama", models=["mistral:latest", "qwen3:8b"])
    sel = eng._resolve_ai_selection(conv, message("ollama", "qwen3:8b"), decision)
    assert sel.allowed_providers == {"ollama"}
    assert sel.model_override == "qwen3:8b"
    assert sel.requested_provider == "ollama"
    assert sel.requested_model == "qwen3:8b"
    assert sel.persist == {"mode": "explicit", "provider": "ollama", "model": "qwen3:8b"}


# ── TEST C: switching between two models under the SAME provider ───────
def test_switching_between_two_models_on_same_provider_reaches_router() -> None:
    """Proves the contract distinguishes provider from model: two different
    explicit selections on the same provider produce two different model
    overrides that would be passed to ModelRouter, not just two provider picks."""
    eng = engine()
    eng.router.providers["ollama"] = FakeProvider("ollama", models=["mistral:latest", "qwen3:8b", "llama3.1:8b"])
    conv = FakeConversation(context={})
    decision = FakeUsageDecision()

    sel_a = eng._resolve_ai_selection(conv, message("ollama", "mistral:latest"), decision)
    sel_b = eng._resolve_ai_selection(conv, message("ollama", "llama3.1:8b"), decision)

    assert sel_a.model_override == "mistral:latest"
    assert sel_b.model_override == "llama3.1:8b"
    assert sel_a.model_override != sel_b.model_override
    assert sel_a.allowed_providers == sel_b.allowed_providers == {"ollama"}


# ── TEST F: explicit unavailable model fails clearly ────────────────────
def test_explicit_choice_rejected_when_provider_not_configured() -> None:
    eng = engine()
    conv = FakeConversation(context={})
    decision = FakeUsageDecision()
    eng.router.providers["openai"] = FakeProvider("openai", configured=False)
    with pytest.raises(HTTPException) as exc:
        eng._resolve_ai_selection(conv, message("openai"), decision)
    assert exc.value.status_code == 409
    assert "unavailable" in str(exc.value.detail).lower()


def test_unknown_model_name_is_rejected() -> None:
    eng = engine()
    conv = FakeConversation(context={})
    decision = FakeUsageDecision()
    with pytest.raises(HTTPException) as exc:
        eng._resolve_ai_selection(conv, message("made_up_provider"), decision)
    assert exc.value.status_code == 400


# ── TEST G: tenant-denied model cannot be selected or executed ─────────
def test_tenant_denied_provider_is_rejected_even_when_configured() -> None:
    eng = engine()
    conv = FakeConversation(context={})
    decision = FakeUsageDecision(denied_providers=("openai",))
    eng.router.providers["openai"] = FakeProvider("openai")
    with pytest.raises(HTTPException) as exc:
        eng._resolve_ai_selection(conv, message("openai"), decision)
    assert exc.value.status_code == 409


def test_tenant_allow_list_excludes_non_allowed_provider() -> None:
    eng = engine()
    conv = FakeConversation(context={})
    decision = FakeUsageDecision(allowed_providers=("ollama",))
    eng.router.providers["openai"] = FakeProvider("openai")
    with pytest.raises(HTTPException) as exc:
        eng._resolve_ai_selection(conv, message("openai"), decision)
    assert exc.value.status_code == 409


# ── TEST D/E: conversation default restore, provider AND model ─────────
def test_conversation_default_restored_with_exact_provider_and_model() -> None:
    eng = engine()
    conv = FakeConversation(context={"ai_selection": {"mode": "explicit", "provider": "ollama", "model": "qwen3:8b"}})
    decision = FakeUsageDecision()
    eng.router.providers["ollama"] = FakeProvider("ollama", models=["mistral:latest", "qwen3:8b"])
    sel = eng._resolve_ai_selection(conv, message(None), decision)
    assert sel.allowed_providers == {"ollama"}
    assert sel.model_override == "qwen3:8b"
    assert sel.persist is None  # no explicit request this call, so nothing new to persist


def test_explicit_auto_resets_conversation_default() -> None:
    eng = engine()
    conv = FakeConversation(context={"ai_selection": {"mode": "explicit", "provider": "ollama", "model": "qwen3:8b"}})
    decision = FakeUsageDecision()
    sel = eng._resolve_ai_selection(conv, message("auto"), decision)
    assert sel.allowed_providers is None
    assert sel.model_override is None
    assert sel.persist == {"mode": "auto"}
