"""Long-term memory CRUD.

Memories are only ever created explicitly (via the API) -- nothing in the
system persists a message into long-term memory automatically. This is a
deliberate privacy choice (see docs/architecture.md / master spec section 19).
"""
from __future__ import annotations

import uuid
from typing import Any, cast

from sqlalchemy import CursorResult, delete, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.database.models import Memory

VALID_MEMORY_TYPES = {"temporary", "conversation", "useful", "persistent", "sensitive"}


async def create_memory(
    session: AsyncSession,
    *,
    content: str,
    memory_type: str = "useful",
    source: str | None = None,
    embedding: list[float] | None = None,
    metadata: dict[str, Any] | None = None,
) -> Memory:
    if memory_type not in VALID_MEMORY_TYPES:
        raise ValueError(f"Invalid memory_type '{memory_type}'; must be one of {VALID_MEMORY_TYPES}")

    memory = Memory(
        content=content,
        memory_type=memory_type,
        source=source,
        embedding=embedding,
        memory_metadata=metadata or {},
    )
    session.add(memory)
    await session.flush()
    return memory


async def get_memory(session: AsyncSession, memory_id: uuid.UUID) -> Memory | None:
    return await session.get(Memory, memory_id)


async def list_memories(
    session: AsyncSession, *, memory_type: str | None = None, limit: int = 200
) -> list[Memory]:
    query = select(Memory).order_by(Memory.created_at.desc()).limit(limit)
    if memory_type is not None:
        query = query.where(Memory.memory_type == memory_type)
    result = await session.execute(query)
    return list(result.scalars().all())


async def delete_memory(session: AsyncSession, memory_id: uuid.UUID) -> bool:
    memory = await session.get(Memory, memory_id)
    if memory is None:
        return False
    await session.delete(memory)
    return True


async def delete_all_memories(session: AsyncSession) -> int:
    # A DELETE statement's result is always a CursorResult at runtime (it
    # exposes .rowcount); the generic Result[Any] return type on
    # AsyncSession.execute() just doesn't express that statically.
    result = await session.execute(delete(Memory))
    return cast(CursorResult, result).rowcount or 0
