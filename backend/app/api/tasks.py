"""Task (automation execution history) API."""
from __future__ import annotations

import uuid
from datetime import datetime

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.automation.executor import execute_automation
from app.core.orchestrator import Orchestrator, get_orchestrator
from app.database.database import get_session
from app.database.models import Automation, Task
from app.notifications.manager import NotificationManager, get_notification_manager

router = APIRouter(prefix="/api/tasks", tags=["tasks"])


class TaskOut(BaseModel):
    id: uuid.UUID
    automation_id: uuid.UUID
    title: str
    status: str
    result: str | None
    error: str | None
    created_at: datetime
    started_at: datetime | None
    completed_at: datetime | None

    model_config = {"from_attributes": True}


@router.get("", response_model=list[TaskOut])
async def list_tasks(
    automation_id: uuid.UUID | None = None, session: AsyncSession = Depends(get_session)
) -> list[TaskOut]:
    query = select(Task).order_by(Task.created_at.desc()).limit(200)
    if automation_id is not None:
        query = query.where(Task.automation_id == automation_id)
    result = await session.execute(query)
    return [TaskOut.model_validate(t) for t in result.scalars().all()]


@router.get("/{task_id}", response_model=TaskOut)
async def get_task(task_id: uuid.UUID, session: AsyncSession = Depends(get_session)) -> TaskOut:
    task = await session.get(Task, task_id)
    if task is None:
        raise HTTPException(status_code=404, detail="Task not found")
    return TaskOut.model_validate(task)


@router.post("/{task_id}/retry", response_model=TaskOut)
async def retry_task(
    task_id: uuid.UUID,
    session: AsyncSession = Depends(get_session),
    orchestrator: Orchestrator = Depends(get_orchestrator),
    notification_manager: NotificationManager = Depends(get_notification_manager),
) -> TaskOut:
    task = await session.get(Task, task_id)
    if task is None:
        raise HTTPException(status_code=404, detail="Task not found")
    if task.status != "failed":
        raise HTTPException(status_code=422, detail="Only failed tasks can be retried")

    automation = await session.get(Automation, task.automation_id)
    if automation is None:
        raise HTTPException(status_code=404, detail="The automation that created this task no longer exists")

    new_task = await execute_automation(session, automation, orchestrator, notification_manager)
    return TaskOut.model_validate(new_task)


@router.delete("/{task_id}", status_code=204)
async def delete_task(task_id: uuid.UUID, session: AsyncSession = Depends(get_session)) -> None:
    task = await session.get(Task, task_id)
    if task is None:
        raise HTTPException(status_code=404, detail="Task not found")
    if task.status == "running":
        raise HTTPException(status_code=422, detail="Cannot delete a task that is currently running")
    await session.delete(task)
    await session.commit()
