from __future__ import annotations

from abc import ABC, abstractmethod

from ..contracts import ProviderRequest, ProviderResponse


class ProviderError(RuntimeError):
    def __init__(self, provider: str, message: str, *, code: str = "provider_error") -> None:
        super().__init__(message)
        self.provider = provider
        self.code = code


class AIProvider(ABC):
    name: str

    @property
    @abstractmethod
    def configured(self) -> bool: ...

    @property
    @abstractmethod
    def default_model(self) -> str: ...

    @abstractmethod
    async def generate(self, request: ProviderRequest) -> ProviderResponse: ...
