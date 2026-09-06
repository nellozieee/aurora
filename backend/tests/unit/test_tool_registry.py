"""Unit tests for app.tools.registry.ToolRegistry.

Corresponds to spec section 70's "tool registry" unit-test requirement.
"""
from __future__ import annotations

import pytest
from pydantic import BaseModel

from app.tools.base import PermissionLevel, RiskLevel, ToolDefinition, ToolResult
from app.tools.registry import ToolRegistry


class _Args(BaseModel):
    pass


async def _handler(_args: _Args) -> ToolResult:
    return ToolResult.ok()


def _tool(name: str) -> ToolDefinition:
    return ToolDefinition(
        name=name,
        description="test tool",
        args_model=_Args,
        risk_level=RiskLevel.SAFE,
        permission_level=PermissionLevel.SAFE,
        handler=_handler,
    )


def test_register_and_get():
    registry = ToolRegistry()
    registry.register(_tool("my_tool"))
    found = registry.get("my_tool")
    assert found is not None
    assert found.name == "my_tool"


def test_get_unknown_tool_returns_none():
    registry = ToolRegistry()
    assert registry.get("does_not_exist") is None


def test_duplicate_registration_raises():
    registry = ToolRegistry()
    registry.register(_tool("dup"))
    with pytest.raises(ValueError):
        registry.register(_tool("dup"))


def test_list_all_returns_every_registered_tool():
    registry = ToolRegistry()
    registry.register(_tool("a"))
    registry.register(_tool("b"))
    names = {t.name for t in registry.list_all()}
    assert names == {"a", "b"}


def test_input_schema_reflects_args_model():
    registry = ToolRegistry()
    tool = _tool("schema_test")
    registry.register(tool)
    schema = registry.get("schema_test").input_schema()
    assert schema["title"] == "_Args"
