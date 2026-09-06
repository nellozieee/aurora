"""Memory CRUD + semantic search API."""
from __future__ import annotations

import uuid
from datetime import datetime
from typing import Any

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel
from sqlalchemy.ext.asyncio import AsyncSession

from app.ai.router import AIRouter, get_ai_router
from app.core.config import Settings, get_settings
from app.database.database import get_session
from app.database.models import Memory
from app.memory import long_term
from app.memory.long_term import VALID_MEMORY_TYPES
from app.memory.semantic import EmbeddingUnavailableError, embed_text, similarity_search

router = APIRouter(prefix="/api/memory", tags=["memory"])


class MemoryCreate(BaseModel):
    content: str
    memory_type: str = "useful"
    source: str | None = None
    metadata: dict[str, Any] | None = None


class MemoryOut(BaseModel):
    id: uuid.UUID
    content: str
    memory_type: str
    source: str | None
    metadata: dict[str, Any]
    embedded: bool
    created_at: datetime
    updated_at: datetime

    @staticmethod
    def from_model(memory: Memory) -> MemoryOut:
        return MemoryOut(
            id=memory.id,
            content=memory.content,
            memory_type=memory.memory_type,
            source=memory.source,
            metadata=memory.memory_metadata,
            embedded=memory.embedding is not None,
            created_at=memory.created_at,
            updated_at=memory.updated_at,
        )


class MemorySearchResult(MemoryOut):
    distance: float


@router.post("", response_model=MemoryOut, status_code=201)
async def create_memory(
    body: MemoryCreate,
    session: AsyncSession = Depends(get_session),
    ai_router: AIRouter = Depends(get_ai_router),
    settings: Settings = Depends(get_settings),
) -> MemoryOut:
    if body.memory_type not in VALID_MEMORY_TYPES:
        raise HTTPException(
            status_code=422, detail=f"memory_type must be one of {sorted(VALID_MEMORY_TYPES)}"
        )

    embedding: list[float] | None = None
    try:
        embedding = await embed_text(ai_router, settings, body.content)
    except EmbeddingUnavailableError:
        pass  # store the memory anyway; it just won't be semantically searchable

    memory = await long_term.create_memory(
        session,
        content=body.content,
        memory_type=body.memory_type,
        source=body.source,
        embedding=embedding,
        metadata=body.metadata,
    )
    await session.commit()
    await session.refresh(memory)
    return MemoryOut.from_model(memory)


@router.get("")
async def list_or_search_memories(
    q: str | None = Query(default=None, description="Semantic search query"),
    memory_type: str | None = Query(default=None),
    top_k: int = Query(default=10, ge=1, le=50),
    session: AsyncSession = Depends(get_session),
    ai_router: AIRouter = Depends(get_ai_router),
    settings: Settings = Depends(get_settings),
) -> list[MemoryOut] | list[MemorySearchResult]:
    if q:
        try:
            query_embedding = await embed_text(ai_router, settings, q)
        except EmbeddingUnavailableError as exc:
            raise HTTPException(status_code=503, detail=f"Semantic search unavailable: {exc}") from exc

        matches = await similarity_search(session, query_embedding, top_k=top_k)
        results = [
            MemorySearchResult(**MemoryOut.from_model(m).model_dump(), distance=distance)
            for m, distance in matches
        ]
        if memory_type is not None:
            results = [r for r in results if r.memory_type == memory_type]
        return results

    memories = await long_term.list_memories(session, memory_type=memory_type, limit=top_k * 20)
    return [MemoryOut.from_model(m) for m in memories]


@router.get("/{memory_id}", response_model=MemoryOut)
async def get_memory(memory_id: uuid.UUID, session: AsyncSession = Depends(get_session)) -> MemoryOut:
    memory = await long_term.get_memory(session, memory_id)
    if memory is None:
        raise HTTPException(status_code=404, detail="Memory not found")
    return MemoryOut.from_model(memory)


@router.delete("/{memory_id}", status_code=204)
async def delete_memory(memory_id: uuid.UUID, session: AsyncSession = Depends(get_session)) -> None:
    deleted = await long_term.delete_memory(session, memory_id)
    if not deleted:
        raise HTTPException(status_code=404, detail="Memory not found")
    await session.commit()


@router.delete("", status_code=200)
async def delete_all_memories(session: AsyncSession = Depends(get_session)) -> dict[str, int]:
    count = await long_term.delete_all_memories(session)
    await session.commit()
    return {"deleted": count}
