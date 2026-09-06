"""Embedding generation and pgvector similarity search."""
from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.ai.router import AIRouter
from app.ai.schemas import ProviderRequestError, ProviderUnavailableError
from app.core.config import Settings
from app.database.models import Memory


class EmbeddingUnavailableError(Exception):
    """Raised when no embedding provider/model is configured or reachable."""


async def embed_text(ai_router: AIRouter, settings: Settings, text: str) -> list[float]:
    provider_name = settings.memory_embedding_provider or settings.ai_default_provider
    model = settings.memory_embedding_model or None
    try:
        provider = ai_router.get_provider(provider_name)
        result = await provider.embedding(text, model=model)
    except (ProviderUnavailableError, ProviderRequestError, NotImplementedError) as exc:
        raise EmbeddingUnavailableError(str(exc)) from exc

    if len(result.vector) != settings.memory_embedding_dimensions:
        raise EmbeddingUnavailableError(
            f"Embedding model '{result.model}' returned {len(result.vector)} dimensions, "
            f"but MEMORY_EMBEDDING_DIMENSIONS is {settings.memory_embedding_dimensions}. "
            "Update MEMORY_EMBEDDING_DIMENSIONS (and re-run migrations) to match the model."
        )
    return result.vector


async def similarity_search(
    session: AsyncSession,
    query_embedding: list[float],
    *,
    top_k: int = 5,
    max_distance: float | None = None,
    exclude_memory_types: list[str] | None = None,
) -> list[tuple[Memory, float]]:
    """Return (memory, cosine_distance) pairs ordered by closeness (lower = closer)."""
    distance = Memory.embedding.cosine_distance(query_embedding)
    query = select(Memory, distance.label("distance")).where(Memory.embedding.is_not(None))

    if exclude_memory_types:
        query = query.where(Memory.memory_type.not_in(exclude_memory_types))

    query = query.order_by(distance).limit(top_k)

    result = await session.execute(query)
    rows = result.all()

    if max_distance is not None:
        rows = [row for row in rows if row.distance <= max_distance]

    return [(row.Memory, row.distance) for row in rows]
