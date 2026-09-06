"""Text-to-speech provider abstraction.

`local` (pyttsx3, OS-native voices via Windows SAPI5) needs no API key;
`openai` is an optional cloud alternative.
"""
from __future__ import annotations

import asyncio
import tempfile
from abc import ABC, abstractmethod
from functools import lru_cache
from pathlib import Path
from uuid import uuid4

import httpx
from pydantic import BaseModel

from app.core.config import Settings, get_settings


class TTSResult(BaseModel):
    audio_bytes: bytes
    content_type: str
    provider: str


class TTSUnavailableError(Exception):
    pass


class TTSProvider(ABC):
    name: str

    @abstractmethod
    async def is_available(self) -> bool: ...

    @abstractmethod
    async def synthesize(self, text: str) -> TTSResult: ...


class LocalTTSProvider(TTSProvider):
    """pyttsx3 over the OS's native voices (SAPI5 on Windows). A fresh engine
    is created per call rather than shared -- pyttsx3 engines aren't
    reliably safe to reuse across concurrent calls."""

    name = "local"

    def __init__(self, settings: Settings) -> None:
        self._settings = settings

    async def is_available(self) -> bool:
        return True

    def _synthesize_sync(self, text: str) -> bytes:
        import pyttsx3

        engine = pyttsx3.init()
        try:
            base_rate = engine.getProperty("rate") or 200
            engine.setProperty("rate", int(base_rate * self._settings.tts_speed))

            if self._settings.tts_voice:
                for voice in engine.getProperty("voices"):
                    if self._settings.tts_voice.lower() in (voice.id + voice.name).lower():
                        engine.setProperty("voice", voice.id)
                        break

            out_path = Path(tempfile.gettempdir()) / f"aurora_tts_{uuid4().hex}.wav"
            engine.save_to_file(text, str(out_path))
            engine.runAndWait()
            try:
                return out_path.read_bytes()
            finally:
                out_path.unlink(missing_ok=True)
        finally:
            engine.stop()

    async def synthesize(self, text: str) -> TTSResult:
        try:
            audio = await asyncio.to_thread(self._synthesize_sync, text)
        except Exception as exc:
            raise TTSUnavailableError(f"Local speech synthesis failed: {exc}") from exc
        return TTSResult(audio_bytes=audio, content_type="audio/wav", provider=self.name)


class OpenAITTSProvider(TTSProvider):
    name = "openai"

    def __init__(self, settings: Settings) -> None:
        self._api_key = settings.openai_api_key
        self._voice = settings.tts_voice or "alloy"
        self._speed = settings.tts_speed

    async def is_available(self) -> bool:
        return bool(self._api_key)

    async def synthesize(self, text: str) -> TTSResult:
        if not self._api_key:
            raise TTSUnavailableError("OpenAI TTS is not configured (missing API key)")

        try:
            async with httpx.AsyncClient(timeout=60.0) as client:
                response = await client.post(
                    "https://api.openai.com/v1/audio/speech",
                    headers={"Authorization": f"Bearer {self._api_key}"},
                    json={
                        "model": "tts-1",
                        "voice": self._voice,
                        "input": text,
                        "speed": max(0.25, min(4.0, self._speed)),
                    },
                )
        except httpx.HTTPError as exc:
            raise TTSUnavailableError(f"OpenAI TTS request failed: {exc}") from exc

        if response.status_code >= 400:
            raise TTSUnavailableError(f"OpenAI TTS returned HTTP {response.status_code}: {response.text[:300]}")

        return TTSResult(audio_bytes=response.content, content_type="audio/mpeg", provider=self.name)


@lru_cache
def get_tts_provider() -> TTSProvider:
    settings = get_settings()
    if settings.tts_provider == "openai":
        return OpenAITTSProvider(settings)
    return LocalTTSProvider(settings)
