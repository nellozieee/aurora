"""Shared data structures for the AI provider abstraction."""
from __future__ import annotations

from collections.abc import AsyncIterator
from typing import Any, Literal

from pydantic import BaseModel, Field

Role = Literal["system", "user", "assistant", "tool"]


class ToolCall(BaseModel):
    id: str
    name: str
    arguments: dict[str, Any]


class ChatMessage(BaseModel):
    role: Role
    content: str
    # Set on an assistant message that requested tool calls.
    tool_calls: list[ToolCall] | None = None
    # Set on a role="tool" message: which tool_call this is the result of.
    tool_call_id: str | None = None
    # Set on a role="tool" message: the tool's name (some providers want it).
    name: str | None = None


class ToolDefinition(BaseModel):
    """Model-facing description of a callable tool (JSON-schema function calling)."""

    name: str
    description: str
    parameters: dict[str, Any] = Field(default_factory=dict)


class ChatResult(BaseModel):
    """Result of a non-streaming chat completion."""

    content: str | None = None
    tool_calls: list[ToolCall] = Field(default_factory=list)
    provider: str
    model: str
    finish_reason: str | None = None
    prompt_tokens: int | None = None
    completion_tokens: int | None = None


class StreamChunk(BaseModel):
    """A single incremental piece of a streaming chat completion."""

    delta: str = ""
    done: bool = False
    finish_reason: str | None = None


class EmbeddingResult(BaseModel):
    vector: list[float]
    provider: str
    model: str


ChatStream = AsyncIterator[StreamChunk]


class ProviderUnavailableError(Exception):
    """Raised when a provider is not configured or unreachable."""


class ProviderRequestError(Exception):
    """Raised when a configured provider rejects or fails a request."""
