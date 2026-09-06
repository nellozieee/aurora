"""Reminder/automation tools + direct notifications.

`create_reminder` takes a concrete ISO-8601 timestamp rather than a vague
phrase like "in 5 minutes" -- the agent computes that itself from the real
current time injected into its system prompt (see
app/agents/base.py::build_core_system_prompt), so parsing natural-language
time expressions isn't duplicated/guessed here.
"""
from __future__ import annotations

import uuid
from datetime import UTC, datetime
from zoneinfo import ZoneInfo

from pydantic import BaseModel, Field
from sqlalchemy import select

from app.automation.triggers import InvalidTriggerError, compute_next_run
from app.core.config import get_settings
from app.database.database import session_scope
from app.database.models import Automation
from app.notifications.manager import get_notification_manager
from app.tools.base import PermissionLevel, RiskLevel, ToolDefinition, ToolResult
from app.tools.registry import ToolRegistry
from app.utils.time import utc_now


class CreateReminderArgs(BaseModel):
    message: str = Field(description="What to remind the user about")
    run_at: str = Field(description="ISO-8601 timestamp of when to fire, e.g. '2026-09-05T18:30:00'")


def _to_utc_naive(run_at: datetime) -> datetime:
    """The agent is told the current time in *local* time (see
    build_core_system_prompt) and computes run_at relative to that -- so an
    un-suffixed (naive) timestamp here means local time, not UTC. Everything
    stored/compared in the scheduler is naive-UTC, so convert explicitly
    rather than assuming naive == UTC (that assumption was a real bug: a
    reminder computed this way never became "due" because it was off by the
    local UTC offset)."""
    if run_at.tzinfo is not None:
        return run_at.astimezone(UTC).replace(tzinfo=None)

    settings = get_settings()
    local_tz = ZoneInfo(settings.app_timezone) if settings.app_timezone else datetime.now().astimezone().tzinfo
    return run_at.replace(tzinfo=local_tz).astimezone(UTC).replace(tzinfo=None)


async def create_reminder(args: CreateReminderArgs) -> ToolResult:
    try:
        run_at = datetime.fromisoformat(args.run_at)
    except ValueError as exc:
        return ToolResult.fail("INVALID_TIMESTAMP", f"'{args.run_at}' is not a valid ISO-8601 timestamp: {exc}")

    run_at = _to_utc_naive(run_at)

    if run_at <= utc_now():
        return ToolResult.fail("TIME_IN_PAST", f"{args.run_at} is not in the future")

    automation = Automation(
        name=args.message[:80],
        trigger_type="once",
        run_at=run_at,
        action_type="reminder",
        action_payload={"message": args.message},
        status="active",
    )
    try:
        next_run_at = compute_next_run(automation)
    except InvalidTriggerError as exc:
        return ToolResult.fail("INVALID_TRIGGER", str(exc))
    # A freshly created 'once' automation (no last_run_at yet) always has a
    # concrete next run time -- compute_next_run only returns None for a
    # 'once' trigger that has *already* fired, which this one hasn't.
    assert next_run_at is not None
    automation.next_run_at = next_run_at

    async with session_scope() as session:
        session.add(automation)
        await session.commit()
        await session.refresh(automation)

    return ToolResult.ok(
        data={
            "automation_id": str(automation.id),
            "message": args.message,
            "scheduled_for": next_run_at.isoformat(),
        }
    )


class NoArgs(BaseModel):
    pass


async def list_reminders(_: NoArgs) -> ToolResult:
    async with session_scope() as session:
        result = await session.execute(
            select(Automation)
            .where(Automation.status == "active", Automation.action_type == "reminder")
            .order_by(Automation.next_run_at)
        )
        reminders = result.scalars().all()

    return ToolResult.ok(
        data={
            "reminders": [
                {
                    "automation_id": str(r.id),
                    "message": r.action_payload.get("message", r.name),
                    "scheduled_for": r.next_run_at.isoformat() if r.next_run_at else None,
                }
                for r in reminders
            ]
        }
    )


class CancelReminderArgs(BaseModel):
    automation_id: str


async def cancel_reminder(args: CancelReminderArgs) -> ToolResult:
    try:
        automation_uuid = uuid.UUID(args.automation_id)
    except ValueError:
        return ToolResult.fail("INVALID_ID", f"'{args.automation_id}' is not a valid automation id")

    async with session_scope() as session:
        automation = await session.get(Automation, automation_uuid)
        if automation is None:
            return ToolResult.fail("NOT_FOUND", f"No automation with id {args.automation_id}")
        automation.status = "cancelled"
        await session.commit()

    return ToolResult.ok(data={"automation_id": args.automation_id, "status": "cancelled"})


class SendNotificationArgs(BaseModel):
    title: str
    message: str


async def send_notification(args: SendNotificationArgs) -> ToolResult:
    results = await get_notification_manager().send(args.title, args.message)
    succeeded = [r.provider for r in results if r.success]
    if not succeeded:
        detail = "; ".join(f"{r.provider}: {r.error}" for r in results) or "no notification channel is configured"
        return ToolResult.fail("NO_CHANNEL_AVAILABLE", detail)
    return ToolResult.ok(data={"sent_via": succeeded})


def register(registry: ToolRegistry) -> None:
    registry.register(
        ToolDefinition(
            name="create_reminder",
            description=(
                "Schedule a one-time reminder that notifies the user at a specific future time. "
                "Compute run_at from the current date/time given in your system prompt."
            ),
            args_model=CreateReminderArgs,
            risk_level=RiskLevel.LOW,
            permission_level=PermissionLevel.SAFE,
            handler=create_reminder,
        )
    )
    registry.register(
        ToolDefinition(
            name="list_reminders",
            description="List currently scheduled (active) reminders.",
            args_model=NoArgs,
            risk_level=RiskLevel.SAFE,
            permission_level=PermissionLevel.SAFE,
            handler=list_reminders,
        )
    )
    registry.register(
        ToolDefinition(
            name="cancel_reminder",
            description="Cancel a scheduled reminder by its automation_id.",
            args_model=CancelReminderArgs,
            risk_level=RiskLevel.LOW,
            permission_level=PermissionLevel.SAFE,
            handler=cancel_reminder,
        )
    )
    registry.register(
        ToolDefinition(
            name="send_notification",
            description=(
                "Send an immediate notification to the user (desktop and/or Telegram, "
                "whichever is configured)."
            ),
            args_model=SendNotificationArgs,
            risk_level=RiskLevel.LOW,
            permission_level=PermissionLevel.SAFE,
            handler=send_notification,
        )
    )
