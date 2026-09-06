"""Shared implementation for OpenAI-compatible chat-completions APIs.

Both OpenAIProvider and OpenRouterProvider talk to the same request/response
shape (`POST /chat/completions`), so the HTTP plumbing lives here once.
"""
from __future__ import annotations

import json
from collections.abc import AsyncIterator

import httpx

from app.ai.base import AIProvider
from app.ai.errors import describe_httpx_error
from app.ai.schemas import (
    ChatMessage,
    ChatResult,
    EmbeddingResult,
    ProviderRequestError,
    ProviderUnavailableError,
    StreamChunk,
    ToolCall,
    ToolDefinition,
)


class OpenAICompatibleProvider(AIProvider):
    def __init__(
        self,
        *,
        name: str,
        api_key: str,
        base_url: str,
        default_model: str,
        timeout_seconds: float = 60.0,
        extra_headers: dict[str, str] | None = None,
    ) -> None:
        self.name = name
        self._api_key = api_key
        self._base_url = base_url.rstrip("/")
        self._default_model = default_model
        self._timeout = timeout_seconds
        self._extra_headers = extra_headers or {}

    def _headers(self) -> dict[str, str]:
        return {
            "Authorization": f"Bearer {self._api_key}",
            "Content-Type": "application/json",
            **self._extra_headers,
        }

    async def is_available(self) -> bool:
        return bool(self._api_key)

    @staticmethod
    def _to_openai_messages(messages: list[ChatMessage]) -> list[dict]:
        result = []
        for m in messages:
            entry: dict = {"role": m.role, "content": m.content}
            if m.tool_calls:
                entry["tool_calls"] = [
                    {
                        "id": tc.id,
                        "type": "function",
                        "function": {"name": tc.name, "arguments": json.dumps(tc.arguments)},
                    }
                    for tc in m.tool_calls
                ]
            if m.tool_call_id:
                entry["tool_call_id"] = m.tool_call_id
            if m.name:
                entry["name"] = m.name
            result.append(entry)
        return result

    @staticmethod
    def _to_openai_tools(tools: list[ToolDefinition] | None) -> list[dict] | None:
        if not tools:
            return None
        return [
            {
                "type": "function",
                "function": {
                    "name": t.name,
                    "description": t.description,
                    "parameters": t.parameters,
                },
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
        payload: dict = {
            "model": model or self._default_model,
            "messages": self._to_openai_messages(messages),
            "stream": stream,
        }
        if temperature is not None:
            payload["temperature"] = temperature
        openai_tools = self._to_openai_tools(tools)
        if openai_tools:
            payload["tools"] = openai_tools
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
            raise ProviderUnavailableError(f"{self.name} is not configured (missing API key)")

        payload = self._build_payload(messages, model, tools, temperature, stream=False)

        try:
            async with httpx.AsyncClient(timeout=self._timeout) as client:
                response = await client.post(
                    f"{self._base_url}/chat/completions",
                    headers=self._headers(),
                    json=payload,
                )
        except httpx.HTTPError as exc:
            raise ProviderRequestError(f"{self.name} request failed: {describe_httpx_error(exc)}") from exc

        if response.status_code >= 400:
            raise ProviderRequestError(
                f"{self.name} returned HTTP {response.status_code}: {response.text[:500]}"
            )

        data = response.json()
        choice = data["choices"][0]
        message = choice["message"]
        tool_calls = [
            ToolCall(
                id=tc["id"],
                name=tc["function"]["name"],
                arguments=json.loads(tc["function"]["arguments"] or "{}"),
            )
            for tc in message.get("tool_calls") or []
        ]
        usage = data.get("usage") or {}

        return ChatResult(
            content=message.get("content"),
            tool_calls=tool_calls,
            provider=self.name,
            model=data.get("model", payload["model"]),
            finish_reason=choice.get("finish_reason"),
            prompt_tokens=usage.get("prompt_tokens"),
            completion_tokens=usage.get("completion_tokens"),
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
            raise ProviderUnavailableError(f"{self.name} is not configured (missing API key)")

        payload = self._build_payload(messages, model, tools, temperature, stream=True)

        try:
            async with httpx.AsyncClient(timeout=self._timeout) as client:
                async with client.stream(
                    "POST",
                    f"{self._base_url}/chat/completions",
                    headers=self._headers(),
                    json=payload,
                ) as response:
                    if response.status_code >= 400:
                        body = await response.aread()
                        raise ProviderRequestError(
                            f"{self.name} returned HTTP {response.status_code}: {body[:500]!r}"
                        )
                    async for line in response.aiter_lines():
                        if not line.startswith("data:"):
                            continue
                        data_str = line[len("data:") :].strip()
                        if data_str == "[DONE]":
                            yield StreamChunk(delta="", done=True)
                            return
                        chunk = json.loads(data_str)
                        choice = chunk["choices"][0]
                        delta = choice.get("delta", {}).get("content") or ""
                        finish_reason = choice.get("finish_reason")
                        yield StreamChunk(
                            delta=delta, done=finish_reason is not None, finish_reason=finish_reason
                        )
        except httpx.HTTPError as exc:
            raise ProviderRequestError(f"{self.name} stream failed: {describe_httpx_error(exc)}") from exc

    async def embedding(self, text: str, *, model: str | None = None) -> EmbeddingResult:
        if not self._api_key:
            raise ProviderUnavailableError(f"{self.name} is not configured (missing API key)")

        embed_model = model or "text-embedding-3-small"
        try:
            async with httpx.AsyncClient(timeout=self._timeout) as client:
                response = await client.post(
                    f"{self._base_url}/embeddings",
                    headers=self._headers(),
                    json={"model": embed_model, "input": text},
                )
        except httpx.HTTPError as exc:
            raise ProviderRequestError(f"{self.name} embedding request failed: {describe_httpx_error(exc)}") from exc

        if response.status_code >= 400:
            raise ProviderRequestError(
                f"{self.name} returned HTTP {response.status_code}: {response.text[:500]}"
            )

        data = response.json()
        vector = data["data"][0]["embedding"]
        return EmbeddingResult(vector=vector, provider=self.name, model=embed_model)

    async def vision(self, image_bytes: bytes, prompt: str, *, model: str | None = None) -> str:
        if not self._api_key:
            raise ProviderUnavailableError(f"{self.name} is not configured (missing API key)")

        import base64

        b64 = base64.b64encode(image_bytes).decode("ascii")
        payload = {
            "model": model or self._default_model,
            "messages": [
                {
                    "role": "user",
                    "content": [
                        {"type": "text", "text": prompt},
                        {"type": "image_url", "image_url": {"url": f"data:image/png;base64,{b64}"}},
                    ],
                }
            ],
        }
        try:
            async with httpx.AsyncClient(timeout=self._timeout) as client:
                response = await client.post(
                    f"{self._base_url}/chat/completions", headers=self._headers(), json=payload
                )
        except httpx.HTTPError as exc:
            raise ProviderRequestError(f"{self.name} vision request failed: {describe_httpx_error(exc)}") from exc

        if response.status_code >= 400:
            raise ProviderRequestError(
                f"{self.name} returned HTTP {response.status_code}: {response.text[:500]}"
            )

        data = response.json()
        return data["choices"][0]["message"].get("content") or ""
