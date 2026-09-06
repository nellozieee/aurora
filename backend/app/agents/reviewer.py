"""Reviewer agent: checks step results before a complex task's final response.

If review parsing fails, `review_results` degrades to an approved=True
pass-through with a note explaining the parse failure -- a review hiccup
must never block the user from getting their (already-completed) results.
"""
from __future__ import annotations

import json

from pydantic import BaseModel, ValidationError

from app.agents.base import AgentDefinition
from app.ai.router import AIRouter
from app.ai.schemas import ChatMessage, ProviderRequestError, ProviderUnavailableError

AGENT = AgentDefinition(
    name="reviewer",
    display_name="Reviewer Agent",
    description="Reviews step results for completeness/correctness before finalizing a complex task.",
    system_prompt=(
        "You are Aurora's reviewer agent. You will be given a goal and the "
        "results of each step taken toward it. Judge whether the goal was "
        "actually accomplished, and whether anything looks fabricated or "
        "inconsistent. "
        'Respond with ONLY a JSON object: {"approved": true|false, "notes": "..."}. '
        "No prose, no markdown fences -- JSON only."
    ),
    max_steps=1,
)


class ReviewResult(BaseModel):
    approved: bool
    notes: str


def _extract_json_object(text: str) -> str:
    start = text.find("{")
    end = text.rfind("}")
    if start == -1 or end == -1 or end < start:
        raise ValueError(f"No JSON object found: {text[:200]!r}")
    return text[start : end + 1]


async def review_results(
    ai_router: AIRouter, goal: str, step_summary: str, *, provider: str | None = None
) -> ReviewResult:
    messages = [
        ChatMessage(role="system", content=AGENT.system_prompt),
        ChatMessage(role="user", content=f"Goal: {goal}\n\nStep results:\n{step_summary}"),
    ]
    try:
        result = await ai_router.chat(messages, provider=provider, temperature=0.1)
        payload = json.loads(_extract_json_object(result.content or ""))
        return ReviewResult.model_validate(payload)
    except (ProviderUnavailableError, ProviderRequestError, json.JSONDecodeError, ValidationError, ValueError) as exc:
        return ReviewResult(approved=True, notes=f"(Review step skipped: {exc})")
