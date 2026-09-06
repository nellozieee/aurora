"""Unit tests for AnthropicProvider's message/tool translation.

This is the genuinely novel/risky part of the provider (unlike
OpenAI/Ollama, Anthropic isn't OpenAI-compatible): the system prompt moves
to a separate top-level field, and tool results must be merged into a
single following user message's content blocks rather than sent as
separate messages. No network call is involved -- these are pure
translation-logic tests.
"""
from __future__ import annotations

from app.ai.anthropic_provider import AnthropicProvider
from app.ai.schemas import ChatMessage, ToolCall, ToolDefinition


def test_system_messages_are_extracted_to_a_separate_field():
    messages = [
        ChatMessage(role="system", content="You are a helpful assistant."),
        ChatMessage(role="user", content="Hello"),
    ]
    system, anthropic_messages = AnthropicProvider._to_anthropic_messages(messages)
    assert system == "You are a helpful assistant."
    assert anthropic_messages == [{"role": "user", "content": "Hello"}]


def test_multiple_system_messages_are_joined():
    messages = [
        ChatMessage(role="system", content="First rule."),
        ChatMessage(role="system", content="Second rule."),
        ChatMessage(role="user", content="Hi"),
    ]
    system, _ = AnthropicProvider._to_anthropic_messages(messages)
    assert system == "First rule.\n\nSecond rule."


def test_assistant_tool_calls_become_tool_use_content_blocks():
    messages = [
        ChatMessage(
            role="assistant",
            content="Let me check.",
            tool_calls=[ToolCall(id="call_1", name="get_weather", arguments={"city": "Paris"})],
        ),
    ]
    _, anthropic_messages = AnthropicProvider._to_anthropic_messages(messages)
    assert anthropic_messages == [
        {
            "role": "assistant",
            "content": [
                {"type": "text", "text": "Let me check."},
                {"type": "tool_use", "id": "call_1", "name": "get_weather", "input": {"city": "Paris"}},
            ],
        }
    ]


def test_tool_result_becomes_a_user_message_with_tool_result_block():
    messages = [
        ChatMessage(role="tool", content='{"temp": 20}', tool_call_id="call_1", name="get_weather"),
    ]
    _, anthropic_messages = AnthropicProvider._to_anthropic_messages(messages)
    assert anthropic_messages == [
        {"role": "user", "content": [{"type": "tool_result", "tool_use_id": "call_1", "content": '{"temp": 20}'}]}
    ]


def test_consecutive_tool_results_are_merged_into_one_user_message():
    """Anthropic requires all tool_result blocks answering one assistant
    turn to be merged into a single following user message, not sent as
    separate messages the way this system's role="tool" messages are
    modeled internally."""
    messages = [
        ChatMessage(
            role="assistant",
            content="",
            tool_calls=[
                ToolCall(id="call_1", name="tool_a", arguments={}),
                ToolCall(id="call_2", name="tool_b", arguments={}),
            ],
        ),
        ChatMessage(role="tool", content="result A", tool_call_id="call_1", name="tool_a"),
        ChatMessage(role="tool", content="result B", tool_call_id="call_2", name="tool_b"),
    ]
    _, anthropic_messages = AnthropicProvider._to_anthropic_messages(messages)

    assert len(anthropic_messages) == 2  # assistant turn + one merged user turn
    user_turn = anthropic_messages[1]
    assert user_turn["role"] == "user"
    assert user_turn["content"] == [
        {"type": "tool_result", "tool_use_id": "call_1", "content": "result A"},
        {"type": "tool_result", "tool_use_id": "call_2", "content": "result B"},
    ]


def test_tool_definitions_use_input_schema_not_parameters():
    tools = [
        ToolDefinition(
            name="get_weather",
            description="Get the weather",
            parameters={"type": "object", "properties": {"city": {"type": "string"}}},
        )
    ]
    anthropic_tools = AnthropicProvider._to_anthropic_tools(tools)
    assert anthropic_tools == [
        {
            "name": "get_weather",
            "description": "Get the weather",
            "input_schema": {"type": "object", "properties": {"city": {"type": "string"}}},
        }
    ]


def test_no_tools_returns_none():
    assert AnthropicProvider._to_anthropic_tools(None) is None
    assert AnthropicProvider._to_anthropic_tools([]) is None


def test_tool_with_empty_parameters_gets_a_valid_empty_schema():
    """Anthropic's API rejects a missing/empty input_schema -- always
    provide at least a minimal valid object schema."""
    tools = [ToolDefinition(name="ping", description="No-op", parameters={})]
    anthropic_tools = AnthropicProvider._to_anthropic_tools(tools)
    assert anthropic_tools[0]["input_schema"] == {"type": "object", "properties": {}}


async def test_is_available_reflects_whether_api_key_is_configured():
    from app.core.config import Settings

    configured = AnthropicProvider(Settings(_env_file=None, ANTHROPIC_API_KEY="sk-ant-fake-test-key"))
    assert await configured.is_available() is True

    unconfigured = AnthropicProvider(Settings(_env_file=None, ANTHROPIC_API_KEY=""))
    assert await unconfigured.is_available() is False
