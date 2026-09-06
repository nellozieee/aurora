"""Voice activity detection.

Two independent layers, deliberately not duplicated:

1. **Client-side (primary):** the Voice page uses the Web Audio API's
   `AnalyserNode` to measure real microphone amplitude locally in the
   browser, so it can auto-stop a push-to-talk recording after the user
   stops speaking without ever sending idle silence to the backend. Fully
   local, no network, no model.
2. **Server-side (STT preprocessing):** `LocalWhisperProvider` runs with
   `vad_filter=True` (faster-whisper's bundled Silero VAD), which trims
   non-speech segments from uploaded audio before transcription. This
   module just centralizes the tunable parameters both layers agree on.
"""
from __future__ import annotations

# Silence duration (ms) that faster-whisper's VAD filter treats as a gap
# between speech segments.
MIN_SILENCE_DURATION_MS = 500

# Suggested client-side amplitude threshold (0-1, relative to max volume) and
# how long the mic must stay under it before auto-stopping a recording.
CLIENT_SILENCE_THRESHOLD = 0.02
CLIENT_SILENCE_DURATION_MS = 1500
