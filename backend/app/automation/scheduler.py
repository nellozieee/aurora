"""Persistent background scheduler.

Polls the `automations` table for anything due rather than keeping schedule
state in memory, so scheduled tasks survive a restart: whatever's overdue
when the process comes back up simply fires on the next poll tick.
"""
from __future__ import annotations

import asyncio

from sqlalchemy import select

from app.automation.executor import execute_automation
from app.automation.triggers import compute_next_run
from app.core.orchestrator import get_orchestrator
from app.database.database import session_scope
from app.database.models import Automation
from app.notifications.manager import get_notification_manager
from app.utils.logging import get_logger
from app.utils.time import utc_now

logger = get_logger(__name__)

POLL_INTERVAL_SECONDS = 5.0


async def _tick() -> None:
    orchestrator = get_orchestrator()
    notification_manager = get_notification_manager()
    now = utc_now()

    async with session_scope() as session:
        result = await session.execute(
            select(Automation).where(Automation.status == "active", Automation.next_run_at <= now)
        )
        due = result.scalars().all()

        for automation in due:
            logger.info("scheduler.firing", automation_id=str(automation.id), name=automation.name)
            await execute_automation(session, automation, orchestrator, notification_manager)

            automation.last_run_at = now
            try:
                next_run = compute_next_run(automation, after=now)
            except Exception as exc:
                logger.warning("scheduler.next_run_failed", automation_id=str(automation.id), error=str(exc))
                next_run = None

            if next_run is None:
                automation.status = "completed" if automation.trigger_type == "once" else "cancelled"
                automation.next_run_at = None
            else:
                automation.next_run_at = next_run
            await session.commit()


async def run_forever() -> None:
    logger.info("scheduler.started", poll_interval_seconds=POLL_INTERVAL_SECONDS)
    while True:
        try:
            await _tick()
        except Exception as exc:  # the scheduler loop itself must never die
            logger.warning("scheduler.tick_failed", error=str(exc))
        await asyncio.sleep(POLL_INTERVAL_SECONDS)


_scheduler_task: asyncio.Task | None = None


def start_scheduler() -> None:
    global _scheduler_task
    if _scheduler_task is None:
        _scheduler_task = asyncio.create_task(run_forever())


async def stop_scheduler() -> None:
    global _scheduler_task
    if _scheduler_task is not None:
        _scheduler_task.cancel()
        try:
            await _scheduler_task
        except asyncio.CancelledError:
            pass
        _scheduler_task = None
