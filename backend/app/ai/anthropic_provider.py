"""Anthropic (Claude) provider -- native Messages API.

Unlike OpenAI/OpenRouter, Anthropic's API isn't OpenAI-compatible: the
system prompt is a separate top-level field rather than a message in the
list, tool definitions use `input_schema` instead of a nested `function`
object, and tool results must be sent back as `tool_result` content blocks
inside a *user* message (immediately following the assistant's `tool_use`
blocks) rather than as separate `role="tool"` messages. This provider
translates this system's provider-agnostic `ChatMessage`/`ToolDefinition`
shapes into that format and back.
"""
from __future__ import annotations

import base64
import json
from collections.abc import AsyncIterator

import httpx

from app.ai.base import AIProvider
from app.ai.errors import describe_httpx_error
from app.ai.schemas import (
    ChatMessage,
    ChatResult,
    ProviderRequestError,
    ProviderUnavailableError,
    StreamChunk,
    ToolCall,
    ToolDefinition,
)
from app.core.config import Settings

_API_VERSION = "2023-06-01"
_DEFAULT_MAX_TOKENS = 4096


class AnthropicProvider(AIProvider):
    name = "anthropic"

    def __init__(self, settings: Settings, timeout_seconds: float = 60.0) -> None:
        self._api_key = settings.anthropic_api_key
        self._base_url = settings.anthropic_base_url.rstrip("/")
        self._default_model = settings.anthropic_model
        self._timeout = timeout_seconds

    async def is_available(self) -> bool:
        return bool(self._api_key)

    def _headers(self) -> dict[str, str]:
        return {
            "x-api-key": self._api_key,
            "anthropic-version": _API_VERSION,
            "content-type": "application/json",
        }

    @staticmethod
    def _to_anthropic_messages(messages: list[ChatMessage]) -> tuple[str, list[dict]]:
        """Returns (system_prompt, messages). Anthropic keeps the system
        prompt as a separate top-level field, and requires every tool
        result following one assistant turn to be merged into a single
        user message's content blocks (not sent as separate messages)."""
        system_parts: list[str] = []
        result: list[dict] = []

        for m in messages:
            if m.role == "system":
                system_parts.append(m.content)
                continue

            if m.role == "tool":
                block = {"type": "tool_result", "tool_use_id": m.tool_call_id, "content": m.content}
                last = result[-1] if result else None
                if (
                    last is not None
                    and last["role"] == "user"
                    and all(c.get("type") == "tool_result" for c in last["content"])
                ):
                    last["content"].append(block)
                else:
                    result.append({"role": "user", "content": [block]})
                continue

            if m.role == "assistant" and m.tool_calls:
                content: list[dict] = []
                if m.content:
                    content.append({"type": "text", "text": m.content})
                for tc in m.tool_calls:
                    content.append({"type": "tool_use", "id": tc.id, "name": tc.name, "input": tc.arguments})
                result.append({"role": "assistant", "content": content})
                continue

            result.append({"role": m.role, "content": m.content})

        return "\n\n".join(system_parts), result

    @staticmethod
    def _to_anthropic_tools(tools: list[ToolDefinition] | None) -> list[dict] | None:
        if not tools:
            return None
        return [
            {
                "name": t.name,
                "description": t.description,
                "input_schema": t.parameters or {"type": "object", "properties": {}},
            }
            for t in tools
        ]

    def _build_payload(
        self,
        messages: list[ChatMessage],
        model: str | None,
        tools: list[ToolDefinition] | None,
        temperature: float | None,
        stream: bool,
    ) -> dict:
        system, anthropic_messages = self._to_anthropic_messages(messages)
        payload: dict = {
            "model": model or self._default_model,
            "max_tokens": _DEFAULT_MAX_TOKENS,
            "messages": anthropic_messages,
            "stream": stream,
        }
        if system:
            payload["system"] = system
        if temperature is not None:
            payload["temperature"] = temperature
        anthropic_tools = self._to_anthropic_tools(tools)
        if anthropic_tools:
            payload["tools"] = anthropic_tools
        return payload

    async def chat(
        self,
        messages: list[ChatMessage],
        *,
        model: str | None = None,
        tools: list[ToolDefinition] | None = None,
        temperature: float | None = None,
    ) -> ChatResult:
        if not self._api_key:
            raise ProviderUnavailableError("anthropic is not configured (missing API key)")

        payload = self._build_payload(messages, model, tools, temperature, stream=False)
        try:
            async with httpx.AsyncClient(timeout=self._timeout) as client:
                response = await client.post(
                    f"{self._base_url}/v1/messages", headers=self._headers(), json=payload
                )
        except httpx.HTTPError as exc:
            raise ProviderRequestError(f"anthropic request failed: {describe_httpx_error(exc)}") from exc

        if response.status_code >= 400:
            raise ProviderRequestError(
                f"anthropic returned HTTP {response.status_code}: {response.text[:500]}"
            )

        data = response.json()
        text_parts: list[str] = []
        tool_calls: list[ToolCall] = []
        for block in data.get("content", []):
            if block["type"] == "text":
                text_parts.append(block["text"])
            elif block["type"] == "tool_use":
                tool_calls.append(
                    ToolCall(id=block["id"], name=block["name"], arguments=block.get("input", {}))
                )

        usage = data.get("usage") or {}
        return ChatResult(
            content="".join(text_parts) or None,
            tool_calls=tool_calls,
            provider=self.name,
            model=data.get("model", payload["model"]),
            finish_reason=data.get("stop_reason"),
            prompt_tokens=usage.get("input_tokens"),
            completion_tokens=usage.get("output_tokens"),
        )

    async def stream_chat(
        self,
        messages: list[ChatMessage],
        *,
        model: str | None = None,
        tools: list[ToolDefinition] | None = None,
        temperature: float | None = None,
    ) -> AsyncIterator[StreamChunk]:
        if not self._api_key:
            raise ProviderUnavailableError("anthropic is not configured (missing API key)")

        payload = self._build_payload(messages, model, tools, temperature, stream=True)
        try:
            async with httpx.AsyncClient(timeout=self._timeout) as client:
                async with client.stream(
                    "POST", f"{self._base_url}/v1/messages", headers=self._headers(), json=payload
                ) as response:
                    if response.status_code >= 400:
                        body = await response.aread()
                        raise ProviderRequestError(
                            f"anthropic returned HTTP {response.status_code}: {body[:500]!r}"
                        )
                    async for line in response.aiter_lines():
                        if not line.startswith("data:"):
                            continue
                        data_str = line[len("data:") :].strip()
                        if not data_str:
                            continue
                        event = json.loads(data_str)
                        etype = event.get("type")
                        if etype == "content_block_delta":
                            delta = event.get("delta", {})
                            if delta.get("type") == "text_delta":
                                yield StreamChunk(delta=delta.get("text", ""))
                        elif etype == "message_delta":
                            stop_reason = event.get("delta", {}).get("stop_reason")
                            if stop_reason:
                                yield StreamChunk(delta="", done=True, finish_reason=stop_reason)
                        elif etype == "message_stop":
                            yield StreamChunk(delta="", done=True)
                            return
        except httpx.HTTPError as exc:
            raise ProviderRequestError(f"anthropic stream failed: {describe_httpx_error(exc)}") from exc

    async def vision(self, image_bytes: bytes, prompt: str, *, model: str | None = None) -> str:
        if not self._api_key:
            raise ProviderUnavailableError("anthropic is not configured (missing API key)")

        b64 = base64.b64encode(image_bytes).decode("ascii")
        payload = {
            "model": model or self._default_model,
            "max_tokens": _DEFAULT_MAX_TOKENS,
            "messages": [
                {
                    "role": "user",
                    "content": [
                        {
                            "type": "image",
                            "source": {"type": "base64", "media_type": "image/png", "data": b64},
                        },
                        {"type": "text", "text": prompt},
                    ],
                }
            ],
        }
        try:
            async with httpx.AsyncClient(timeout=self._timeout) as client:
                response = await client.post(
                    f"{self._base_url}/v1/messages", headers=self._headers(), json=payload
                )
        except httpx.HTTPError as exc:
            raise ProviderRequestError(f"anthropic vision request failed: {describe_httpx_error(exc)}") from exc

        if response.status_code >= 400:
            raise ProviderRequestError(
                f"anthropic returned HTTP {response.status_code}: {response.text[:500]}"
            )

        data = response.json()
        return "".join(b["text"] for b in data.get("content", []) if b.get("type") == "text")

    # Anthropic has no embeddings endpoint -- embedding() is intentionally
    # not overridden, so it raises the base class's NotImplementedError.
