"""AI provider router.

Selects a provider based on configuration (`AI_DEFAULT_PROVIDER`) and falls
back to `AI_FALLBACK_PROVIDER` -- only when the user has explicitly
configured one -- if the primary provider is unreachable or misconfigured.
"""
from __future__ import annotations

from functools import lru_cache

from app.ai.anthropic_provider import AnthropicProvider
from app.ai.base import AIProvider
from app.ai.ollama_provider import OllamaProvider
from app.ai.openai_provider import OpenAIProvider
from app.ai.openrouter_provider import OpenRouterProvider
from app.ai.schemas import (
    ChatMessage,
    ChatResult,
    ChatStream,
    ProviderRequestError,
    ProviderUnavailableError,
    ToolDefinition,
)
from app.core.config import Settings, get_settings
from app.utils.logging import get_logger

logger = get_logger(__name__)


class UnknownProviderError(Exception):
    pass


class AIRouter:
    def __init__(self, settings: Settings) -> None:
        self._settings = settings
        self._providers: dict[str, AIProvider] = {
            "openai": OpenAIProvider(settings),
            "openrouter": OpenRouterProvider(settings),
            "anthropic": AnthropicProvider(settings),
            "ollama": OllamaProvider(settings),
        }

    def get_provider(self, name: str) -> AIProvider:
        try:
            return self._providers[name]
        except KeyError as exc:
            raise UnknownProviderError(f"Unknown AI provider: {name}") from exc

    async def provider_statuses(self) -> dict[str, str]:
        statuses: dict[str, str] = {}
        for name, provider in self._providers.items():
            try:
                statuses[name] = "online" if await provider.is_available() else "not_configured"
            except Exception:  # defensive: a provider check must never break /status
                statuses[name] = "error"
        return statuses

    def _resolution_order(self, requested_provider: str | None) -> list[str]:
        primary = requested_provider or self._settings.ai_default_provider
        order = [primary]
        fallback = self._settings.ai_fallback_provider
        if fallback and fallback != primary:
            order.append(fallback)
        return order

    async def chat(
        self,
        messages: list[ChatMessage],
        *,
        provider: str | None = None,
        model: str | None = None,
        tools: list[ToolDefinition] | None = None,
        temperature: float | None = None,
    ) -> ChatResult:
        last_error: Exception | None = None
        for name in self._resolution_order(provider):
            candidate = self.get_provider(name)
            try:
                return await candidate.chat(
                    messages, model=model, tools=tools, temperature=temperature
                )
            except (ProviderUnavailableError, ProviderRequestError) as exc:
                logger.warning("ai_router.provider_failed", provider=name, error=str(exc))
                last_error = exc
                continue
        raise ProviderUnavailableError(
            f"No configured AI provider could handle the request (last error: {last_error})"
        )

    async def stream_chat(
        self,
        messages: list[ChatMessage],
        *,
        provider: str | None = None,
        model: str | None = None,
        tools: list[ToolDefinition] | None = None,
        temperature: float | None = None,
    ) -> tuple[str, ChatStream]:
        """Return (provider_name, stream). Falls back before any tokens are sent,
        never mid-stream, so a partial response is never silently discarded."""
        last_error: Exception | None = None
        for name in self._resolution_order(provider):
            candidate = self.get_provider(name)
            if not await candidate.is_available():
                last_error = ProviderUnavailableError(f"{name} is not configured")
                continue
            return name, candidate.stream_chat(
                messages, model=model, tools=tools, temperature=temperature
            )
        raise ProviderUnavailableError(
            f"No configured AI provider could handle the request (last error: {last_error})"
        )


@lru_cache
def get_ai_router() -> AIRouter:
    return AIRouter(get_settings())
