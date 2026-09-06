"""Speech-to-text provider abstraction.

`local` (faster-whisper) needs no API key and is the default; `openai` is an
optional cloud alternative. Both fail with a clear, structured error rather
than a fabricated transcript if something goes wrong.
"""
from __future__ import annotations

import asyncio
from abc import ABC, abstractmethod
from functools import lru_cache
from pathlib import Path
from typing import TYPE_CHECKING

import httpx
from pydantic import BaseModel

from app.core.config import Settings, get_settings

if TYPE_CHECKING:
    from faster_whisper import WhisperModel


class STTResult(BaseModel):
    text: str
    provider: str
    model: str
    language: str | None = None
    duration_seconds: float | None = None


class STTUnavailableError(Exception):
    pass


class STTProvider(ABC):
    name: str

    @abstractmethod
    async def is_available(self) -> bool: ...

    @abstractmethod
    async def transcribe(self, audio_path: Path) -> STTResult: ...


class LocalWhisperProvider(STTProvider):
    """faster-whisper, running fully on-device -- no API key, no network
    once the model is downloaded once."""

    name = "local"

    def __init__(self, settings: Settings) -> None:
        self._settings = settings
        self._model: WhisperModel | None = None  # lazy-loaded on first use (loading takes ~0.5s)

    async def is_available(self) -> bool:
        return True

    def _model_dir(self) -> Path:
        return self._settings.voice_models_path / f"faster-whisper-{self._settings.stt_model}"

    def _ensure_downloaded(self) -> Path:
        target = self._model_dir()
        if (target / "model.bin").exists():
            return target

        import huggingface_hub

        target.mkdir(parents=True, exist_ok=True)
        huggingface_hub.snapshot_download(
            repo_id=f"Systran/faster-whisper-{self._settings.stt_model}",
            local_dir=str(target),
        )
        return target

    def _load_model(self) -> WhisperModel:
        from faster_whisper import WhisperModel

        model_path = self._ensure_downloaded()
        return WhisperModel(str(model_path), device="cpu", compute_type="int8")

    def _transcribe_sync(self, audio_path: Path) -> STTResult:
        # A local variable, not `self._model` directly -- mypy doesn't
        # narrow an Optional instance attribute's type past a reassignment
        # the way it narrows a local variable.
        model = self._model
        if model is None:
            model = self._model = self._load_model()

        segments, info = model.transcribe(str(audio_path), vad_filter=True)
        text = " ".join(segment.text.strip() for segment in segments).strip()
        return STTResult(
            text=text,
            provider=self.name,
            model=self._settings.stt_model,
            language=info.language,
            duration_seconds=info.duration,
        )

    async def transcribe(self, audio_path: Path) -> STTResult:
        try:
            return await asyncio.to_thread(self._transcribe_sync, audio_path)
        except Exception as exc:
            raise STTUnavailableError(f"Local transcription failed: {exc}") from exc


class OpenAIWhisperProvider(STTProvider):
    name = "openai"

    def __init__(self, settings: Settings) -> None:
        self._api_key = settings.openai_api_key
        self._model = "whisper-1"

    async def is_available(self) -> bool:
        return bool(self._api_key)

    async def transcribe(self, audio_path: Path) -> STTResult:
        if not self._api_key:
            raise STTUnavailableError("OpenAI STT is not configured (missing API key)")

        try:
            async with httpx.AsyncClient(timeout=60.0) as client:
                with audio_path.open("rb") as f:
                    response = await client.post(
                        "https://api.openai.com/v1/audio/transcriptions",
                        headers={"Authorization": f"Bearer {self._api_key}"},
                        data={"model": self._model},
                        files={"file": (audio_path.name, f, "application/octet-stream")},
                    )
        except httpx.HTTPError as exc:
            raise STTUnavailableError(f"OpenAI STT request failed: {exc}") from exc

        if response.status_code >= 400:
            raise STTUnavailableError(f"OpenAI STT returned HTTP {response.status_code}: {response.text[:300]}")

        data = response.json()
        return STTResult(text=data.get("text", "").strip(), provider=self.name, model=self._model)


@lru_cache
def get_stt_provider() -> STTProvider:
    """Process-wide singleton so LocalWhisperProvider's loaded model is reused
    across requests instead of reloading it every call."""
    settings = get_settings()
    if settings.stt_provider == "openai":
        return OpenAIWhisperProvider(settings)
    return LocalWhisperProvider(settings)
