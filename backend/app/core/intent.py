"""Lightweight intent classification.

Classification always has a safe fallback: any failure (provider
unavailable, unparseable response) resolves to "conversation" rather than
raising -- an intent-classification hiccup must never block a chat reply.
"""
from __future__ import annotations

from typing import Literal, get_args

from app.ai.router import AIRouter
from app.ai.schemas import ChatMessage
from app.utils.logging import get_logger

logger = get_logger(__name__)

Intent = Literal[
    "conversation",
    "question",
    "research",
    "coding",
    "file_operation",
    "computer_control",
    "system_information",
    "memory",
    "automation",
    "unknown",
]

_VALID_INTENTS: set[str] = set(get_args(Intent))

_CLASSIFIER_PROMPT = (
    "Classify the user's message into exactly one label from this list:\n"
    f"{', '.join(sorted(_VALID_INTENTS))}\n\n"
    "- research: wants information looked up / summarized from the WEB (an "
    "external, online source)\n"
    "- coding: wants code written, debugged, explained, or run\n"
    "- file_operation: wants a LOCAL file read, searched, or summarized -- "
    "if the message names a filename or says 'this file'/'the file', it is "
    "file_operation even if the verb is 'summarize'\n"
    "- computer_control: wants an application opened/closed, or process "
    "info -- classify as computer_control even if the message adds extra "
    "commentary about why (e.g. 'open X, then close it, just testing Y')\n"
    "- system_information: asks about this machine's status/specs\n"
    "- memory: wants something remembered, recalled, or forgotten\n"
    "- automation: wants a reminder scheduled/listed/cancelled, or a notification sent\n"
    "- question: a factual question answerable from general knowledge\n"
    "- conversation: casual chat, greetings, opinions, anything else\n"
    "- unknown: genuinely unclear\n\n"
    "Respond with ONLY the single label word, nothing else."
)


async def classify_intent(ai_router: AIRouter, message: str, *, provider: str | None = None) -> Intent:
    try:
        result = await ai_router.chat(
            [
                ChatMessage(role="system", content=_CLASSIFIER_PROMPT),
                ChatMessage(role="user", content=message),
            ],
            provider=provider,
            temperature=0.0,
        )
    except Exception as exc:  # classification must never break the chat request
        logger.debug("intent.classification_failed", error=str(exc))
        return "conversation"

    label = (result.content or "").strip().lower().strip(".")
    # A small/local model may wrap the label in a short sentence; take the
    # first token that matches a known label rather than requiring an exact
    # full-string match.
    for word in label.split():
        cleaned = word.strip(".,:;\"'")
        if cleaned in _VALID_INTENTS:
            return cleaned  # type: ignore[return-value]

    logger.debug("intent.unrecognized_label", label=label)
    return "conversation"
