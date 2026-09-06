"""Short-term memory: the current conversation's message history."""
from __future__ import annotations

import uuid
from typing import cast

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.ai.schemas import ChatMessage, Role
from app.database.models import Message


async def get_recent_messages(
    session: AsyncSession, conversation_id: uuid.UUID, limit: int | None = None
) -> list[ChatMessage]:
    """Return a conversation's messages in chronological order.

    `limit`, when given, keeps only the most recent `limit` messages (still
    returned oldest-first) -- a simple guard against unbounded context growth
    until conversation summarization is implemented.
    """
    query = select(Message).where(Message.conversation_id == conversation_id).order_by(
        Message.created_at
    )
    result = await session.execute(query)
    messages = list(result.scalars().all())
    if limit is not None and len(messages) > limit:
        messages = messages[-limit:]
    # Message.role is an unconstrained Text column, but this codebase only
    # ever writes "system"/"user"/"assistant"/"tool" into it -- the DB
    # schema doesn't express that invariant the way ChatMessage.role does.
    return [ChatMessage(role=cast(Role, m.role), content=m.content) for m in messages]
