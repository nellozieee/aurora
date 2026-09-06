"""The assistant orchestrator -- the central brain tying everything together.

Per turn: classify intent, select an agent, retrieve relevant memory, decide
whether the request needs a multi-step plan, run it, and (for complex tasks)
review the result before returning it. The orchestrator never touches a tool
directly -- that's the agents' + ToolRouter's job.
"""
from __future__ import annotations

import uuid
from collections.abc import AsyncIterator
from functools import lru_cache

from sqlalchemy.ext.asyncio import AsyncSession

from app.agents import planning, reviewer
from app.agents.base import AgentRunner
from app.agents.events import (
    AgentErrorEvent,
    AgentSelectedEvent,
    AssistantDeltaEvent,
    FinalEvent,
    IntentClassifiedEvent,
    OrchestratorEvent,
    PlanCreatedEvent,
    ReviewEvent,
    StepCompletedEvent,
    StepStartedEvent,
    ToolCompletedEvent,
)
from app.agents.planning import PlanningError
from app.agents.registry import get_agent
from app.ai.router import AIRouter, get_ai_router
from app.ai.schemas import ChatMessage
from app.core.config import Settings, get_settings
from app.core.intent import Intent, classify_intent
from app.database.models import AgentRun, ToolExecution
from app.memory.retrieval import format_memories_for_prompt, get_relevant_memories
from app.tools.registry import ToolRegistry, get_tool_registry
from app.tools.router import ToolRouter
from app.utils.logging import get_logger
from app.utils.time import utc_now

logger = get_logger(__name__)

_INTENT_TO_AGENT: dict[str, str] = {
    "research": "research",
    "coding": "coding",
    "computer_control": "computer",
    "system_information": "computer",
    "file_operation": "general",
    "memory": "general",
    "automation": "general",
    "question": "general",
    "conversation": "general",
    "unknown": "general",
}

_COMPLEXITY_MARKERS = (" and then ", "step by step", "step-by-step", "after that", " then ", "first,")


def _select_agent_name(intent: Intent) -> str:
    return _INTENT_TO_AGENT.get(intent, "general")


def _looks_complex(message: str, intent: Intent) -> bool:
    if intent == "research":
        return True
    lowered = message.lower()
    return any(marker in lowered for marker in _COMPLEXITY_MARKERS)


class Orchestrator:
    def __init__(
        self,
        ai_router: AIRouter,
        tool_registry: ToolRegistry,
        tool_router: ToolRouter,
        settings: Settings,
    ) -> None:
        self._ai_router = ai_router
        self._tool_registry = tool_registry
        self._tool_router = tool_router
        self._settings = settings

    async def handle_message(
        self,
        session: AsyncSession,
        conversation_id: uuid.UUID,
        history: list[ChatMessage],
        user_message: str,
        *,
        provider: str | None = None,
        model: str | None = None,
        image_context: str | None = None,
    ) -> AsyncIterator[OrchestratorEvent]:
        """Run one turn and persist an AgentRun + ToolExecution audit trail.

        This is the observability half of the orchestrator's job (section 10:
        "observe results", "handle errors") -- it wraps `_generate_events`
        rather than duplicating agent-selection logic.
        """
        agent_run = AgentRun(conversation_id=conversation_id, agent_name="", status="running")
        session.add(agent_run)
        await session.flush()
        await session.commit()

        steps_taken = 0
        error_text: str | None = None

        try:
            async for event in self._generate_events(
                session, user_message, history, provider=provider, model=model, image_context=image_context
            ):
                if isinstance(event, AgentSelectedEvent):
                    agent_run.agent_name = event.agent
                elif isinstance(event, IntentClassifiedEvent):
                    agent_run.intent = event.intent
                elif isinstance(event, ToolCompletedEvent):
                    steps_taken += 1
                    tool_def = self._tool_registry.get(event.tool)
                    session.add(
                        ToolExecution(
                            agent_run_id=agent_run.id,
                            tool_name=event.tool,
                            risk_level=tool_def.risk_level.value if tool_def else "unknown",
                            success=event.success,
                            error_code=event.result.error.code if event.result.error else None,
                            duration_ms=round(event.result.metadata.get("duration_seconds", 0) * 1000),
                            request_id=str(agent_run.id),
                            arguments_hash=event.arguments_hash,
                            permission_status=event.result.metadata.get("permission_status", "not_required"),
                        )
                    )
                    await session.commit()
                elif isinstance(event, AgentErrorEvent):
                    error_text = event.message
                yield event
        except Exception as exc:  # never let a tracking bug break the actual response
            logger.warning("orchestrator.tracking_error", error=str(exc))
            error_text = error_text or str(exc)
            raise
        finally:
            agent_run.status = "failed" if error_text else "completed"
            agent_run.steps_taken = steps_taken
            agent_run.error = error_text
            agent_run.completed_at = utc_now()
            await session.commit()

    async def _generate_events(
        self,
        session: AsyncSession,
        user_message: str,
        history: list[ChatMessage],
        *,
        provider: str | None,
        model: str | None,
        image_context: str | None = None,
    ) -> AsyncIterator[OrchestratorEvent]:
        intent = await classify_intent(self._ai_router, user_message, provider=provider)
        yield IntentClassifiedEvent(intent=intent)

        agent_name = _select_agent_name(intent)
        agent_def = get_agent(agent_name) or get_agent("general")
        if agent_def is None:
            # Only reachable if "general" itself was removed from the agent
            # registry -- a real misconfiguration, not a normal runtime path.
            # Fail with a clear error here rather than an obscure AttributeError
            # on `.name` two lines down.
            raise RuntimeError("Agent registry misconfigured: no 'general' agent registered")
        yield AgentSelectedEvent(agent=agent_def.name)

        relevant_memories = await get_relevant_memories(session, self._ai_router, self._settings, user_message)
        memory_context = format_memories_for_prompt(relevant_memories)

        base_messages = list(history)
        if memory_context:
            base_messages = [ChatMessage(role="system", content=memory_context), *base_messages]
        if image_context:
            base_messages = [ChatMessage(role="system", content=image_context), *base_messages]

        runner = AgentRunner(agent_def, self._ai_router, self._tool_registry, self._tool_router)

        if _looks_complex(user_message, intent):
            async for event in self._run_complex(runner, base_messages, user_message, provider, model):
                yield event
            return

        working_messages = [*base_messages, ChatMessage(role="user", content=user_message)]
        async for event in runner.run(working_messages, provider=provider, model=model):
            yield event

    async def _run_complex(
        self,
        runner: AgentRunner,
        base_messages: list[ChatMessage],
        user_message: str,
        provider: str | None,
        model: str | None,
    ) -> AsyncIterator[OrchestratorEvent]:
        try:
            plan = await planning.create_plan(self._ai_router, user_message, provider=provider)
        except PlanningError as exc:
            logger.info("orchestrator.plan_fallback", error=str(exc))
            plan = None

        if plan is None or len(plan.steps) <= 1:
            # Planning failed or judged this simple after all -- fall back
            # to direct single-agent execution rather than a fake plan.
            working_messages = [*base_messages, ChatMessage(role="user", content=user_message)]
            async for event in runner.run(working_messages, provider=provider, model=model):
                yield event
            return

        yield PlanCreatedEvent(goal=plan.goal, steps=[s.description for s in plan.steps])

        working_messages = [*base_messages, ChatMessage(role="user", content=user_message)]
        step_outputs: list[str] = []
        final_content, final_provider, final_model = "", "", ""
        aborted = False

        for step in plan.steps:
            yield StepStartedEvent(step_id=step.id, description=step.description)
            working_messages.append(ChatMessage(role="user", content=step.description))

            step_final = ""
            async for event in runner.run(working_messages, provider=provider, model=model):
                if isinstance(event, FinalEvent):
                    # A step's own "final answer" is internal narration, not
                    # the overall response -- capture it, don't stream it.
                    step_final = event.content
                    final_provider, final_model = event.provider, event.model
                elif isinstance(event, AssistantDeltaEvent):
                    continue
                elif isinstance(event, AgentErrorEvent):
                    yield event
                    aborted = True
                else:
                    yield event

            working_messages.append(ChatMessage(role="assistant", content=step_final))
            step_result = step_final or "(no result -- see error above)"
            step_outputs.append(f"Step {step.id} ({step.description}): {step_result}")
            yield StepCompletedEvent(step_id=step.id, result=step_final)

            if aborted:
                break
            final_content = step_final

        review = await reviewer.review_results(
            self._ai_router, user_message, "\n".join(step_outputs), provider=provider
        )
        yield ReviewEvent(approved=review.approved, notes=review.notes)
        if not review.approved:
            final_content = f"{final_content}\n\n(Internal review flagged: {review.notes})"

        if final_content:
            yield FinalEvent(content=final_content, provider=final_provider, model=final_model)


@lru_cache
def get_orchestrator() -> Orchestrator:
    settings = get_settings()
    registry = get_tool_registry()
    return Orchestrator(get_ai_router(), registry, ToolRouter(registry), settings)
