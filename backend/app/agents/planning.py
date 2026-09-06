"""Planning agent: decomposes a complex goal into a structured step plan.

Unlike the other agents, this one doesn't use the tool-calling loop -- it
makes a single structured-output request and parses the result. If parsing
fails, `create_plan` raises `PlanningError` so the orchestrator can fall back
to direct single-agent execution rather than pretending a plan exists.
"""
from __future__ import annotations

import json
from typing import Literal

from pydantic import BaseModel, ValidationError

from app.agents.base import AgentDefinition
from app.ai.router import AIRouter
from app.ai.schemas import ChatMessage, ProviderRequestError, ProviderUnavailableError

AGENT = AgentDefinition(
    name="planning",
    display_name="Planning Agent",
    description="Complex multi-step task decomposition and dependency management.",
    system_prompt=(
        "You are Aurora's planning agent. Given a user's goal, break it into "
        "a short, ordered list of concrete steps another agent can execute. "
        'Respond with ONLY a JSON object of the exact shape: '
        '{"goal": "...", "steps": [{"id": 1, "description": "..."}, ...]}. '
        "No prose, no markdown fences -- JSON only. Keep it to 2-6 steps; "
        "if the goal is actually simple, return a single step."
    ),
    max_steps=1,
)


class PlanStep(BaseModel):
    id: int
    description: str
    status: Literal["pending", "running", "completed", "failed", "cancelled"] = "pending"


class Plan(BaseModel):
    goal: str
    steps: list[PlanStep]


class PlanningError(Exception):
    pass


def _extract_json_object(text: str) -> str:
    start = text.find("{")
    end = text.rfind("}")
    if start == -1 or end == -1 or end < start:
        raise PlanningError(f"No JSON object found in planning response: {text[:200]!r}")
    return text[start : end + 1]


async def create_plan(ai_router: AIRouter, goal: str, *, provider: str | None = None) -> Plan:
    messages = [
        ChatMessage(role="system", content=AGENT.system_prompt),
        ChatMessage(role="user", content=goal),
    ]
    try:
        result = await ai_router.chat(messages, provider=provider, temperature=0.2)
    except (ProviderUnavailableError, ProviderRequestError) as exc:
        raise PlanningError(str(exc)) from exc

    raw = result.content or ""
    try:
        payload = json.loads(_extract_json_object(raw))
        return Plan.model_validate(payload)
    except (json.JSONDecodeError, ValidationError) as exc:
        raise PlanningError(f"Could not parse a valid plan from the model: {exc}") from exc
