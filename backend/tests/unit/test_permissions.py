"""Unit tests for the centralized permission engine (app.security.permissions).

Corresponds to spec section 71's test_delete_requires_confirmation() and the
general "permissions" unit-test requirement in section 70.
"""
from __future__ import annotations

import pytest
from pydantic import BaseModel

from app.security import permissions
from app.tools.base import PermissionLevel, RiskLevel, ToolDefinition, ToolResult


class _Args(BaseModel):
    path: str = "x"


async def _handler(_args: _Args) -> ToolResult:
    return ToolResult.ok()


def _tool(permission_level: PermissionLevel, risk_level: RiskLevel = RiskLevel.HIGH) -> ToolDefinition:
    return ToolDefinition(
        name="delete_file",
        description="test",
        args_model=_Args,
        risk_level=risk_level,
        permission_level=permission_level,
        handler=_handler,
    )


def test_confirm_level_tool_denied_without_confirm_flag():
    tool = _tool(PermissionLevel.CONFIRM)
    with pytest.raises(permissions.PermissionDenied) as exc_info:
        permissions.enforce(tool, {"path": "x"})
    assert exc_info.value.code == "PERMISSION_REQUIRED"


def test_confirm_level_tool_allowed_with_confirm_true():
    tool = _tool(PermissionLevel.CONFIRM)
    permissions.enforce(tool, {"path": "x", "confirm": True})  # must not raise


def test_confirm_level_tool_denied_with_confirm_false_or_truthy_string():
    tool = _tool(PermissionLevel.CONFIRM)
    # Only the literal boolean True grants -- a truthy-looking string must not.
    with pytest.raises(permissions.PermissionDenied):
        permissions.enforce(tool, {"path": "x", "confirm": "true"})
    with pytest.raises(permissions.PermissionDenied):
        permissions.enforce(tool, {"path": "x", "confirm": False})


@pytest.mark.parametrize("level", [PermissionLevel.SAFE, PermissionLevel.USER])
def test_safe_and_user_level_tools_never_blocked(level):
    tool = _tool(level)
    permissions.enforce(tool, {})  # must not raise regardless of arguments


def test_permission_status_not_required_for_non_confirm_tools():
    tool = _tool(PermissionLevel.USER)
    assert permissions.permission_status(tool, denied=False) == "not_required"


def test_permission_status_granted_and_denied_for_confirm_tools():
    tool = _tool(PermissionLevel.CONFIRM)
    assert permissions.permission_status(tool, denied=False) == "granted"
    assert permissions.permission_status(tool, denied=True) == "denied"
