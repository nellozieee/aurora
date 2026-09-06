"""Events emitted while an agent runs, consumed by chat.py to update the UI."""
from __future__ import annotations

from typing import Any, Literal

from pydantic import BaseModel

from app.tools.base import ToolResult


class ToolStartedEvent(BaseModel):
    type: Literal["tool_started"] = "tool_started"
    tool: str
    arguments: dict[str, Any]


class ToolCompletedEvent(BaseModel):
    type: Literal["tool_completed"] = "tool_completed"
    tool: str
    success: bool
    result: ToolResult
    arguments_hash: str = ""


class AssistantDeltaEvent(BaseModel):
    type: Literal["assistant_delta"] = "assistant_delta"
    content: str


class FinalEvent(BaseModel):
    type: Literal["final"] = "final"
    content: str
    provider: str
    model: str


class AgentErrorEvent(BaseModel):
    type: Literal["agent_error"] = "agent_error"
    code: str
    message: str


AgentEvent = ToolStartedEvent | ToolCompletedEvent | AssistantDeltaEvent | FinalEvent | AgentErrorEvent


# ----- Orchestrator-level events (wrap AgentEvent with intent/plan context) -----


class IntentClassifiedEvent(BaseModel):
    type: Literal["intent_classified"] = "intent_classified"
    intent: str


class AgentSelectedEvent(BaseModel):
    type: Literal["agent_selected"] = "agent_selected"
    agent: str


class PlanCreatedEvent(BaseModel):
    type: Literal["plan_created"] = "plan_created"
    goal: str
    steps: list[str]


class StepStartedEvent(BaseModel):
    type: Literal["step_started"] = "step_started"
    step_id: int
    description: str


class StepCompletedEvent(BaseModel):
    type: Literal["step_completed"] = "step_completed"
    step_id: int
    result: str


class ReviewEvent(BaseModel):
    type: Literal["review"] = "review"
    approved: bool
    notes: str


OrchestratorEvent = (
    AgentEvent
    | IntentClassifiedEvent
    | AgentSelectedEvent
    | PlanCreatedEvent
    | StepStartedEvent
    | StepCompletedEvent
    | ReviewEvent
)
