"""Executes an Automation's action when it fires, tracked as a Task."""
from __future__ import annotations

import uuid

from sqlalchemy.ext.asyncio import AsyncSession

from app.core.orchestrator import Orchestrator
from app.database.models import Automation, Conversation, Message, Task
from app.memory.short_term import get_recent_messages
from app.notifications.manager import NotificationManager
from app.utils.logging import get_logger
from app.utils.time import utc_now

logger = get_logger(__name__)


async def _run_reminder(automation: Automation, notification_manager: NotificationManager) -> str:
    message = automation.action_payload.get("message", automation.name)
    results = await notification_manager.send(title=f"Aurora reminder: {automation.name}", message=message)
    succeeded = [r.provider for r in results if r.success]
    if not succeeded:
        detail = "; ".join(f"{r.provider}: {r.error}" for r in results) or "no notification channel is configured"
        raise RuntimeError(f"No notification channel delivered the reminder ({detail})")
    return f"Sent via: {', '.join(succeeded)}"


async def _run_chat_message(
    automation: Automation, session: AsyncSession, orchestrator: Orchestrator, notification_manager: NotificationManager
) -> str:
    message = automation.action_payload.get("message", automation.name)
    conversation_id_raw = automation.action_payload.get("conversation_id")

    if conversation_id_raw:
        conversation = await session.get(Conversation, uuid.UUID(conversation_id_raw))
    else:
        conversation = None

    if conversation is None:
        conversation = Conversation(title=f"Automation: {automation.name}")
        session.add(conversation)
        await session.flush()
        history = []
    else:
        history = await get_recent_messages(session, conversation.id)

    user_message = Message(conversation_id=conversation.id, role="user", content=message)
    session.add(user_message)
    await session.flush()

    final_content = ""
    async for event in orchestrator.handle_message(session, conversation.id, history, message):
        if event.type == "final":
            final_content = event.content  # type: ignore[attr-defined]

    assistant_message = Message(conversation_id=conversation.id, role="assistant", content=final_content)
    session.add(assistant_message)
    await session.flush()

    if automation.action_payload.get("notify_on_completion", True):
        snippet = final_content[:300] + ("..." if len(final_content) > 300 else "")
        await notification_manager.send(title=f"Aurora task done: {automation.name}", message=snippet or "(no output)")

    return final_content


async def execute_automation(
    session: AsyncSession,
    automation: Automation,
    orchestrator: Orchestrator,
    notification_manager: NotificationManager,
) -> Task:
    task = Task(automation_id=automation.id, title=automation.name, status="running", started_at=utc_now())
    session.add(task)
    await session.flush()
    await session.commit()

    try:
        if automation.action_type == "reminder":
            result = await _run_reminder(automation, notification_manager)
        elif automation.action_type == "chat_message":
            result = await _run_chat_message(automation, session, orchestrator, notification_manager)
        else:
            raise ValueError(f"Unknown action_type: {automation.action_type!r}")
        task.status = "completed"
        task.result = result
    except Exception as exc:
        logger.warning("automation.execution_failed", automation_id=str(automation.id), error=str(exc))
        task.status = "failed"
        task.error = str(exc)

    task.completed_at = utc_now()
    await session.commit()
    return task
