"""Unit tests for orchestrator agent-selection / complexity heuristics.

Corresponds to spec section 70's "agent selection" unit-test requirement.
"""
from __future__ import annotations

import pytest

from app.core.orchestrator import _looks_complex, _select_agent_name


@pytest.mark.parametrize(
    "intent,expected_agent",
    [
        ("research", "research"),
        ("coding", "coding"),
        ("computer_control", "computer"),
        ("system_information", "computer"),
        ("file_operation", "general"),
        ("memory", "general"),
        ("automation", "general"),
        ("question", "general"),
        ("conversation", "general"),
        ("unknown", "general"),
        ("some_future_intent_not_yet_mapped", "general"),
    ],
)
def test_select_agent_name_maps_every_intent(intent, expected_agent):
    assert _select_agent_name(intent) == expected_agent


def test_research_intent_is_always_treated_as_complex():
    assert _looks_complex("what's the weather", "research") is True


@pytest.mark.parametrize(
    "message",
    [
        "first, open notepad and then type hello",
        "search the web and then summarize the results",
        "do this step by step",
        "do this step-by-step please",
        "check the weather after that tell me a joke",
    ],
)
def test_multi_step_language_is_treated_as_complex(message):
    assert _looks_complex(message, "conversation") is True


@pytest.mark.parametrize(
    "message",
    [
        "what time is it?",
        "tell me a joke",
        "what's 2 + 2",
    ],
)
def test_simple_single_step_messages_are_not_complex(message):
    assert _looks_complex(message, "conversation") is False
