"""Ollama local-model provider."""
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
from app.core.config import Settings


class OllamaProvider(AIProvider):
    name = "ollama"

    def __init__(self, settings: Settings, timeout_seconds: float = 300.0) -> None:
        self._base_url = settings.ollama_base_url.rstrip("/")
        self._default_model = settings.ollama_model
        self._timeout = timeout_seconds

    async def is_available(self) -> bool:
        try:
            async with httpx.AsyncClient(timeout=2.0) as client:
                response = await client.get(f"{self._base_url}/api/tags")
                return response.status_code == 200
        except httpx.HTTPError:
            return False

    @staticmethod
    def _to_ollama_messages(messages: list[ChatMessage]) -> list[dict]:
        result = []
        for m in messages:
            entry: dict = {"role": m.role, "content": m.content}
            if m.tool_calls:
                entry["tool_calls"] = [
                    {"function": {"name": tc.name, "arguments": tc.arguments}} for tc in m.tool_calls
                ]
            result.append(entry)
        return result

    @staticmethod
    def _to_ollama_tools(tools: list[ToolDefinition] | None) -> list[dict] | None:
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

    @staticmethod
    def _parse_tool_calls(message: dict) -> list[ToolCall]:
        calls = []
        for idx, tc in enumerate(message.get("tool_calls") or []):
            fn = tc.get("function", {})
            arguments = fn.get("arguments", {})
            if isinstance(arguments, str):
                try:
                    arguments = json.loads(arguments or "{}")
                except json.JSONDecodeError:
                    arguments = {}
            calls.append(
                ToolCall(id=str(tc.get("id", idx)), name=fn.get("name", ""), arguments=arguments)
            )
        return calls

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
            "messages": self._to_ollama_messages(messages),
            "stream": stream,
        }
        ollama_tools = self._to_ollama_tools(tools)
        if ollama_tools:
            payload["tools"] = ollama_tools
        if temperature is not None:
            payload["options"] = {"temperature": temperature}
        return payload

    async def chat(
        self,
        messages: list[ChatMessage],
        *,
        model: str | None = None,
        tools: list[ToolDefinition] | None = None,
        temperature: float | None = None,
    ) -> ChatResult:
        payload = self._build_payload(messages, model, tools, temperature, stream=False)

        try:
            async with httpx.AsyncClient(timeout=self._timeout) as client:
                response = await client.post(f"{self._base_url}/api/chat", json=payload)
        except httpx.HTTPError as exc:
            raise ProviderUnavailableError(f"ollama request failed: {describe_httpx_error(exc)}") from exc

        if response.status_code >= 400:
            raise ProviderRequestError(f"ollama returned HTTP {response.status_code}: {response.text[:500]}")

        data = response.json()
        message = data.get("message", {})

        return ChatResult(
            content=message.get("content"),
            tool_calls=self._parse_tool_calls(message),
            provider=self.name,
            model=data.get("model", payload["model"]),
            finish_reason="stop" if data.get("done") else None,
            prompt_tokens=data.get("prompt_eval_count"),
            completion_tokens=data.get("eval_count"),
        )

    async def stream_chat(
        self,
        messages: list[ChatMessage],
        *,
        model: str | None = None,
        tools: list[ToolDefinition] | None = None,
        temperature: float | None = None,
    ) -> AsyncIterator[StreamChunk]:
        payload = self._build_payload(messages, model, tools, temperature, stream=True)

        try:
            async with httpx.AsyncClient(timeout=self._timeout) as client:
                async with client.stream("POST", f"{self._base_url}/api/chat", json=payload) as response:
                    if response.status_code >= 400:
                        body = await response.aread()
                        raise ProviderRequestError(
                            f"ollama returned HTTP {response.status_code}: {body[:500]!r}"
                        )
                    async for line in response.aiter_lines():
                        if not line.strip():
                            continue
                        chunk = json.loads(line)
                        content = chunk.get("message", {}).get("content", "")
                        done = bool(chunk.get("done"))
                        yield StreamChunk(delta=content, done=done, finish_reason="stop" if done else None)
        except httpx.HTTPError as exc:
            raise ProviderUnavailableError(f"ollama stream failed: {describe_httpx_error(exc)}") from exc

    async def embedding(self, text: str, *, model: str | None = None) -> EmbeddingResult:
        embed_model = model or self._default_model
        try:
            async with httpx.AsyncClient(timeout=self._timeout) as client:
                response = await client.post(
                    f"{self._base_url}/api/embeddings",
                    json={"model": embed_model, "prompt": text},
                )
        except httpx.HTTPError as exc:
            raise ProviderUnavailableError(f"ollama embedding request failed: {describe_httpx_error(exc)}") from exc

        if response.status_code >= 400:
            raise ProviderRequestError(f"ollama returned HTTP {response.status_code}: {response.text[:500]}")

        data = response.json()
        return EmbeddingResult(vector=data["embedding"], provider=self.name, model=embed_model)

    async def vision(self, image_bytes: bytes, prompt: str, *, model: str | None = None) -> str:
        import base64

        b64 = base64.b64encode(image_bytes).decode("ascii")
        vision_model = model or self._default_model
        payload = {
            "model": vision_model,
            "messages": [{"role": "user", "content": prompt, "images": [b64]}],
            "stream": False,
        }
        try:
            async with httpx.AsyncClient(timeout=self._timeout) as client:
                response = await client.post(f"{self._base_url}/api/chat", json=payload)
        except httpx.HTTPError as exc:
            raise ProviderUnavailableError(f"ollama vision request failed: {describe_httpx_error(exc)}") from exc

        if response.status_code >= 400:
            raise ProviderRequestError(f"ollama returned HTTP {response.status_code}: {response.text[:500]}")

        data = response.json()
        return data.get("message", {}).get("content") or ""
