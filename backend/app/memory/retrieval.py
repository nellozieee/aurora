"""Unified retrieval used to bring relevant long-term memories into context.

This is deliberately read-only and best-effort: a failure here (no embedding
model configured, provider unreachable, etc.) must never break the calling
request -- it just means no memories are retrieved this turn.
"""
from __future__ import annotations

from sqlalchemy.ext.asyncio import AsyncSession

from app.ai.router import AIRouter
from app.core.config import Settings
from app.database.models import Memory
from app.memory.semantic import EmbeddingUnavailableError, embed_text, similarity_search
from app.utils.logging import get_logger

logger = get_logger(__name__)

# Memories marked "sensitive" are stored and retrievable via the explicit
# Memory API, but are not surfaced automatically into chat context.
_EXCLUDED_FROM_AUTO_CONTEXT = ["sensitive"]


async def get_relevant_memories(
    session: AsyncSession, ai_router: AIRouter, settings: Settings, query_text: str
) -> list[Memory]:
    if settings.memory_privacy_mode:
        return []

    try:
        query_embedding = await embed_text(ai_router, settings, query_text)
    except EmbeddingUnavailableError as exc:
        logger.debug("memory.retrieval_skipped", reason=str(exc))
        return []

    try:
        matches = await similarity_search(
            session,
            query_embedding,
            top_k=settings.memory_retrieval_top_k,
            max_distance=settings.memory_retrieval_max_distance,
            exclude_memory_types=_EXCLUDED_FROM_AUTO_CONTEXT,
        )
    except Exception as exc:  # defensive: retrieval must never break chat
        logger.warning("memory.retrieval_failed", error=str(exc))
        return []

    return [memory for memory, _distance in matches]


def format_memories_for_prompt(memories: list[Memory]) -> str | None:
    if not memories:
        return None
    lines = "\n".join(f"- {m.content}" for m in memories)
    return f"Relevant things you remember about the user:\n{lines}"
