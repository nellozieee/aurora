"""AI provider interface.

Every provider (OpenAI-compatible, OpenRouter, Ollama, Anthropic) implements
this interface so the rest of the system never depends on a specific
vendor's API shape.
"""
from __future__ import annotations

from abc import ABC, abstractmethod

from app.ai.schemas import (
    ChatMessage,
    ChatResult,
    ChatStream,
    EmbeddingResult,
    ToolDefinition,
)


class AIProvider(ABC):
    name: str

    @abstractmethod
    async def is_available(self) -> bool:
        """Cheap reachability/configuration check, used for status reporting."""

    @abstractmethod
    async def chat(
        self,
        messages: list[ChatMessage],
        *,
        model: str | None = None,
        tools: list[ToolDefinition] | None = None,
        temperature: float | None = None,
    ) -> ChatResult:
        """Return a complete chat response."""

    @abstractmethod
    def stream_chat(
        self,
        messages: list[ChatMessage],
        *,
        model: str | None = None,
        tools: list[ToolDefinition] | None = None,
        temperature: float | None = None,
    ) -> ChatStream:
        """Yield incremental `StreamChunk`s as the response is generated."""

    async def generate(self, prompt: str, *, model: str | None = None) -> str:
        """Single-turn text generation, implemented in terms of chat()."""
        result = await self.chat([ChatMessage(role="user", content=prompt)], model=model)
        return result.content or ""

    async def embedding(self, text: str, *, model: str | None = None) -> EmbeddingResult:
        raise NotImplementedError(f"{self.name} does not support embeddings")

    async def vision(self, image_bytes: bytes, prompt: str, *, model: str | None = None) -> str:
        raise NotImplementedError(f"{self.name} does not support vision")
