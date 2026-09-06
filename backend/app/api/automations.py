"""Automation (schedule) CRUD API."""
from __future__ import annotations

import uuid
from datetime import UTC, datetime
from typing import Any

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field, model_validator
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.automation.triggers import InvalidTriggerError, compute_next_run
from app.database.database import get_session
from app.database.models import Automation

router = APIRouter(prefix="/api/automations", tags=["automations"])

_VALID_TRIGGER_TYPES = {"once", "interval", "cron"}
_VALID_ACTION_TYPES = {"reminder", "chat_message"}


class AutomationCreate(BaseModel):
    name: str
    trigger_type: str
    run_at: datetime | None = Field(
        default=None,
        description="UTC if no timezone offset is given (unlike the create_reminder tool, which "
        "assumes the server's local time -- this raw API follows the usual REST convention instead)",
    )
    interval_seconds: int | None = None
    cron_expression: str | None = None
    action_type: str
    action_payload: dict[str, Any] = Field(default_factory=dict)

    @model_validator(mode="after")
    def _validate(self) -> AutomationCreate:
        if self.trigger_type not in _VALID_TRIGGER_TYPES:
            raise ValueError(f"trigger_type must be one of {sorted(_VALID_TRIGGER_TYPES)}")
        if self.action_type not in _VALID_ACTION_TYPES:
            raise ValueError(f"action_type must be one of {sorted(_VALID_ACTION_TYPES)}")
        if self.trigger_type == "once" and self.run_at is None:
            raise ValueError("run_at is required for trigger_type='once'")
        if self.trigger_type == "interval" and not self.interval_seconds:
            raise ValueError("interval_seconds is required for trigger_type='interval'")
        if self.trigger_type == "cron" and not self.cron_expression:
            raise ValueError("cron_expression is required for trigger_type='cron'")
        if self.run_at is not None and self.run_at.tzinfo is not None:
            self.run_at = self.run_at.astimezone(UTC).replace(tzinfo=None)
        return self


class AutomationUpdate(BaseModel):
    status: str | None = None  # active|paused|cancelled


class AutomationOut(BaseModel):
    id: uuid.UUID
    name: str
    trigger_type: str
    run_at: datetime | None
    interval_seconds: int | None
    cron_expression: str | None
    action_type: str
    action_payload: dict[str, Any]
    status: str
    next_run_at: datetime | None
    last_run_at: datetime | None
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}


@router.post("", response_model=AutomationOut, status_code=201)
async def create_automation(
    body: AutomationCreate, session: AsyncSession = Depends(get_session)
) -> AutomationOut:
    automation = Automation(
        name=body.name,
        trigger_type=body.trigger_type,
        run_at=body.run_at,
        interval_seconds=body.interval_seconds,
        cron_expression=body.cron_expression,
        action_type=body.action_type,
        action_payload=body.action_payload,
        status="active",
    )
    try:
        automation.next_run_at = compute_next_run(automation)
    except InvalidTriggerError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc

    session.add(automation)
    await session.commit()
    await session.refresh(automation)
    return AutomationOut.model_validate(automation)


@router.get("", response_model=list[AutomationOut])
async def list_automations(session: AsyncSession = Depends(get_session)) -> list[AutomationOut]:
    result = await session.execute(select(Automation).order_by(Automation.created_at.desc()))
    return [AutomationOut.model_validate(a) for a in result.scalars().all()]


@router.get("/{automation_id}", response_model=AutomationOut)
async def get_automation(
    automation_id: uuid.UUID, session: AsyncSession = Depends(get_session)
) -> AutomationOut:
    automation = await session.get(Automation, automation_id)
    if automation is None:
        raise HTTPException(status_code=404, detail="Automation not found")
    return AutomationOut.model_validate(automation)


@router.patch("/{automation_id}", response_model=AutomationOut)
async def update_automation(
    automation_id: uuid.UUID, body: AutomationUpdate, session: AsyncSession = Depends(get_session)
) -> AutomationOut:
    automation = await session.get(Automation, automation_id)
    if automation is None:
        raise HTTPException(status_code=404, detail="Automation not found")

    if body.status is not None:
        if body.status not in {"active", "paused", "cancelled"}:
            raise HTTPException(status_code=422, detail="status must be one of active, paused, cancelled")
        automation.status = body.status
        if body.status == "active" and automation.next_run_at is None:
            try:
                automation.next_run_at = compute_next_run(automation)
            except InvalidTriggerError as exc:
                raise HTTPException(status_code=422, detail=str(exc)) from exc

    await session.commit()
    await session.refresh(automation)
    return AutomationOut.model_validate(automation)


@router.delete("/{automation_id}", status_code=204)
async def delete_automation(
    automation_id: uuid.UUID, session: AsyncSession = Depends(get_session)
) -> None:
    automation = await session.get(Automation, automation_id)
    if automation is None:
        raise HTTPException(status_code=404, detail="Automation not found")
    await session.delete(automation)
    await session.commit()
