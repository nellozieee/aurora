"""Registry of the tool-calling agents (general/research/coding/computer).

Planning and Reviewer are intentionally not here -- they don't run the
tool-calling loop, and are invoked directly by the orchestrator.
"""
from __future__ import annotations

from app.agents import coding, computer, general, research
from app.agents.base import AgentDefinition

_AGENTS: dict[str, AgentDefinition] = {
    general.AGENT.name: general.AGENT,
    research.AGENT.name: research.AGENT,
    coding.AGENT.name: coding.AGENT,
    computer.AGENT.name: computer.AGENT,
}


def get_agent(name: str) -> AgentDefinition | None:
    return _AGENTS.get(name)


def list_agents() -> list[AgentDefinition]:
    return list(_AGENTS.values())
