"""Voice API: transcription, speech synthesis, and voice configuration.

Actual microphone capture, wake-word listening, and playback happen in the
browser (frontend/src/pages/Voice.tsx) -- this API only does the STT/TTS
processing a browser can't do locally.
"""
from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, UploadFile
from fastapi.responses import Response
from pydantic import BaseModel

from app.core.config import Settings, get_settings
from app.voice.audio import temp_audio_file
from app.voice.stt import STTUnavailableError, get_stt_provider
from app.voice.tts import TTSUnavailableError, get_tts_provider
from app.voice.vad import CLIENT_SILENCE_DURATION_MS, CLIENT_SILENCE_THRESHOLD
from app.voice.wakeword import matches_wake_word

router = APIRouter(prefix="/api/voice", tags=["voice"])

_CONTENT_TYPE_SUFFIX = {
    "audio/webm": ".webm",
    "audio/ogg": ".ogg",
    "audio/wav": ".wav",
    "audio/wave": ".wav",
    "audio/x-wav": ".wav",
    "audio/mpeg": ".mp3",
    "audio/mp4": ".m4a",
}


class TranscribeResponse(BaseModel):
    text: str
    provider: str
    model: str
    language: str | None = None


class SpeakRequest(BaseModel):
    text: str


class WakeWordCheckRequest(BaseModel):
    transcript: str


class WakeWordCheckResponse(BaseModel):
    matches: bool
    wake_word: str


class VoiceConfig(BaseModel):
    voice_enabled: bool
    voice_mode: str
    wake_word: str
    stt_provider: str
    tts_provider: str
    client_silence_threshold: float
    client_silence_duration_ms: int


@router.get("/config", response_model=VoiceConfig)
async def get_voice_config(settings: Settings = Depends(get_settings)) -> VoiceConfig:
    return VoiceConfig(
        voice_enabled=settings.voice_enabled,
        voice_mode=settings.voice_mode,
        wake_word=settings.wake_word,
        stt_provider=settings.stt_provider,
        tts_provider=settings.tts_provider,
        client_silence_threshold=CLIENT_SILENCE_THRESHOLD,
        client_silence_duration_ms=CLIENT_SILENCE_DURATION_MS,
    )


@router.post("/transcribe", response_model=TranscribeResponse)
async def transcribe(
    audio: UploadFile,
    settings: Settings = Depends(get_settings),
) -> TranscribeResponse:
    if not settings.voice_enabled:
        raise HTTPException(status_code=403, detail="Voice is disabled (set VOICE_ENABLED=true)")

    suffix = _CONTENT_TYPE_SUFFIX.get(audio.content_type or "", ".webm")
    data = await audio.read()
    if not data:
        raise HTTPException(status_code=422, detail="No audio data received")

    provider = get_stt_provider()
    async with temp_audio_file(data, suffix) as path:
        try:
            result = await provider.transcribe(path)
        except STTUnavailableError as exc:
            raise HTTPException(status_code=503, detail=str(exc)) from exc

    return TranscribeResponse(
        text=result.text, provider=result.provider, model=result.model, language=result.language
    )


@router.post("/check_wake_word", response_model=WakeWordCheckResponse)
async def check_wake_word(
    request: WakeWordCheckRequest, settings: Settings = Depends(get_settings)
) -> WakeWordCheckResponse:
    """Confirms whether a transcript contains the configured wake word.

    Used to double-check a client-side keyword-spotting hit (e.g. from the
    browser's Web Speech API) against the canonical normalization logic
    before treating it as a real activation.
    """
    return WakeWordCheckResponse(
        matches=matches_wake_word(request.transcript, settings.wake_word),
        wake_word=settings.wake_word,
    )


@router.post("/speak")
async def speak(request: SpeakRequest, settings: Settings = Depends(get_settings)) -> Response:
    if not settings.voice_enabled:
        raise HTTPException(status_code=403, detail="Voice is disabled (set VOICE_ENABLED=true)")
    if not request.text.strip():
        raise HTTPException(status_code=422, detail="text must not be empty")

    provider = get_tts_provider()
    try:
        result = await provider.synthesize(request.text)
    except TTSUnavailableError as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc

    return Response(content=result.audio_bytes, media_type=result.content_type)
