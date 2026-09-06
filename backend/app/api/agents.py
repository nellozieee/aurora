"""Agent listing API."""
from __future__ import annotations

from fastapi import APIRouter
from pydantic import BaseModel

from app.agents.registry import list_agents

router = APIRouter(prefix="/api/agents", tags=["agents"])


class AgentSummary(BaseModel):
    name: str
    display_name: str
    description: str
    allowed_tools: list[str]
    max_steps: int
    max_execution_seconds: float


@router.get("", response_model=list[AgentSummary])
async def get_agents() -> list[AgentSummary]:
    return [
        AgentSummary(
            name=a.name,
            display_name=a.display_name,
            description=a.description,
            allowed_tools=a.allowed_tools,
            max_steps=a.max_steps,
            max_execution_seconds=a.max_execution_seconds,
        )
        for a in list_agents()
    ]
