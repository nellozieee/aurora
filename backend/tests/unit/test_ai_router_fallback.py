"""Unit tests for app.ai.router.AIRouter provider fallback.

Corresponds to spec section 71's test_ai_provider_fallback(). Uses fake
in-memory providers (no real network call to OpenAI/Ollama) so this is a
true unit test of the routing/fallback logic itself.
"""
from __future__ import annotations

import pytest

from app.ai.router import AIRouter
from app.ai.schemas import ChatMessage, ChatResult, ProviderUnavailableError
from app.core.config import Settings


class _FailingProvider:
    async def chat(self, messages, *, model=None, tools=None, temperature=None):
        raise ProviderUnavailableError("primary provider is down")

    async def is_available(self):
        return False


class _WorkingProvider:
    async def chat(self, messages, *, model=None, tools=None, temperature=None):
        return ChatResult(content="hello from fallback", provider="fallback", model="test-model")

    async def is_available(self):
        return True


@pytest.fixture()
def router() -> AIRouter:
    settings = Settings(_env_file=None, AI_DEFAULT_PROVIDER="openai", AI_FALLBACK_PROVIDER="ollama")
    r = AIRouter(settings)
    r._providers["openai"] = _FailingProvider()
    r._providers["ollama"] = _WorkingProvider()
    return r


async def test_falls_back_to_secondary_provider_when_primary_fails(router):
    result = await router.chat([ChatMessage(role="user", content="hi")])
    assert result.content == "hello from fallback"
    assert result.provider == "fallback"


async def test_raises_when_every_configured_provider_fails():
    settings = Settings(_env_file=None, AI_DEFAULT_PROVIDER="openai", AI_FALLBACK_PROVIDER="ollama")
    r = AIRouter(settings)
    r._providers["openai"] = _FailingProvider()
    r._providers["ollama"] = _FailingProvider()
    with pytest.raises(ProviderUnavailableError):
        await r.chat([ChatMessage(role="user", content="hi")])


async def test_no_fallback_configured_does_not_try_a_second_provider():
    settings = Settings(_env_file=None, AI_DEFAULT_PROVIDER="openai", AI_FALLBACK_PROVIDER="")
    r = AIRouter(settings)
    r._providers["openai"] = _FailingProvider()
    r._providers["ollama"] = _WorkingProvider()
    with pytest.raises(ProviderUnavailableError):
        await r.chat([ChatMessage(role="user", content="hi")])


def test_unknown_provider_name_raises():
    from app.ai.router import UnknownProviderError

    settings = Settings(_env_file=None)
    r = AIRouter(settings)
    with pytest.raises(UnknownProviderError):
        r.get_provider("not_a_real_provider")
