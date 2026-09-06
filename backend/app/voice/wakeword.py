"""Wake-word matching.

Primary wake-word detection runs client-side in the browser (the Web Speech
API listening continuously for the phrase) so raw microphone audio isn't
streamed to the backend just to check if someone said "Hey Aurora" -- see
frontend/src/pages/Voice.tsx. This module is the server-side confirmation
check: once the browser *thinks* it heard the wake word, it can send the
short clip here for a real transcription-based confirmation before treating
it as an actual activation, since keyword spotting on-device is prone to
false positives.
"""
from __future__ import annotations

import re


def _normalize(text: str) -> str:
    return re.sub(r"[^a-z0-9\s]", "", text.lower()).strip()


def matches_wake_word(transcript: str, wake_word: str) -> bool:
    """Fuzzy-contains check: ignores case/punctuation, allows the wake word
    to appear anywhere in the transcript (not just as an exact prefix)."""
    normalized_transcript = _normalize(transcript)
    normalized_wake_word = _normalize(wake_word)
    if not normalized_wake_word:
        return False
    return normalized_wake_word in normalized_transcript
