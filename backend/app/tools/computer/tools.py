"""Mouse/keyboard control tools.

Every action here requires both `SECURITY_COMPUTER_CONTROL_ENABLED=true`
(a hard opt-in, off by default) and its own `confirm=true` argument, the
latter enforced centrally by `app.security.permissions.enforce()` (called
from `ToolRouter.execute`, not by these handlers) -- except
`move_mouse`/`focus_window`, which only move the cursor or change window
focus and don't themselves act on anything.
"""
from __future__ import annotations

import asyncio

from pydantic import BaseModel, Field

from app.core.config import get_settings
from app.system import get_platform_adapter
from app.system.base import FocusWindowError
from app.tools.base import PermissionLevel, RiskLevel, ToolDefinition, ToolResult
from app.tools.computer.control import (
    InvalidActionError,
    ScreenBoundsError,
    click,
    double_click,
    move_mouse,
    press_key,
    scroll,
    type_text,
)
from app.tools.registry import ToolRegistry


def _disabled_result() -> ToolResult:
    return ToolResult.fail(
        "COMPUTER_CONTROL_DISABLED",
        "Computer control is disabled (set SECURITY_COMPUTER_CONTROL_ENABLED=true to enable).",
    )


class ClickArgs(BaseModel):
    x: int
    y: int
    button: str = Field(default="left", pattern="^(left|right|middle)$")
    confirm: bool = False


async def click_tool(args: ClickArgs) -> ToolResult:
    if not get_settings().security_computer_control_enabled:
        return _disabled_result()
    try:
        await asyncio.to_thread(click, args.x, args.y, args.button)
    except ScreenBoundsError as exc:
        return ToolResult.fail("OUT_OF_BOUNDS", str(exc))
    return ToolResult.ok(data={"x": args.x, "y": args.y, "button": args.button})


class DoubleClickArgs(BaseModel):
    x: int
    y: int
    confirm: bool = False


async def double_click_tool(args: DoubleClickArgs) -> ToolResult:
    if not get_settings().security_computer_control_enabled:
        return _disabled_result()
    try:
        await asyncio.to_thread(double_click, args.x, args.y)
    except ScreenBoundsError as exc:
        return ToolResult.fail("OUT_OF_BOUNDS", str(exc))
    return ToolResult.ok(data={"x": args.x, "y": args.y})


class MoveMouseArgs(BaseModel):
    x: int
    y: int


async def move_mouse_tool(args: MoveMouseArgs) -> ToolResult:
    if not get_settings().security_computer_control_enabled:
        return _disabled_result()
    try:
        await asyncio.to_thread(move_mouse, args.x, args.y)
    except ScreenBoundsError as exc:
        return ToolResult.fail("OUT_OF_BOUNDS", str(exc))
    return ToolResult.ok(data={"x": args.x, "y": args.y})


class TypeTextArgs(BaseModel):
    text: str
    confirm: bool = False


async def type_text_tool(args: TypeTextArgs) -> ToolResult:
    if not get_settings().security_computer_control_enabled:
        return _disabled_result()
    try:
        await asyncio.to_thread(type_text, args.text)
    except InvalidActionError as exc:
        return ToolResult.fail("INVALID_ACTION", str(exc))
    return ToolResult.ok(data={"characters_typed": len(args.text)})


class PressKeyArgs(BaseModel):
    key: str = Field(description="A key name (e.g. 'enter') or '+'-joined combo (e.g. 'ctrl+c')")
    confirm: bool = False


async def press_key_tool(args: PressKeyArgs) -> ToolResult:
    if not get_settings().security_computer_control_enabled:
        return _disabled_result()
    try:
        await asyncio.to_thread(press_key, args.key)
    except InvalidActionError as exc:
        return ToolResult.fail("INVALID_ACTION", str(exc))
    return ToolResult.ok(data={"key": args.key})


class ScrollArgs(BaseModel):
    amount: int = Field(description="Positive scrolls up, negative scrolls down")
    x: int | None = None
    y: int | None = None


async def scroll_tool(args: ScrollArgs) -> ToolResult:
    if not get_settings().security_computer_control_enabled:
        return _disabled_result()
    try:
        await asyncio.to_thread(scroll, args.amount, args.x, args.y)
    except ScreenBoundsError as exc:
        return ToolResult.fail("OUT_OF_BOUNDS", str(exc))
    return ToolResult.ok(data={"amount": args.amount})


class FocusWindowArgs(BaseModel):
    title_substring: str


async def focus_window_tool(args: FocusWindowArgs) -> ToolResult:
    if not get_settings().security_computer_control_enabled:
        return _disabled_result()
    adapter = get_platform_adapter()
    try:
        window = await asyncio.to_thread(adapter.focus_window, args.title_substring)
    except FocusWindowError as exc:
        return ToolResult.fail("FOCUS_FAILED", str(exc))
    return ToolResult.ok(data=window.model_dump())


def register(registry: ToolRegistry) -> None:
    registry.register(
        ToolDefinition(
            name="click",
            description="Click at specific screen coordinates. Requires confirm=true.",
            args_model=ClickArgs,
            risk_level=RiskLevel.HIGH,
            permission_level=PermissionLevel.CONFIRM,
            handler=click_tool,
        )
    )
    registry.register(
        ToolDefinition(
            name="double_click",
            description="Double-click at specific screen coordinates. Requires confirm=true.",
            args_model=DoubleClickArgs,
            risk_level=RiskLevel.HIGH,
            permission_level=PermissionLevel.CONFIRM,
            handler=double_click_tool,
        )
    )
    registry.register(
        ToolDefinition(
            name="move_mouse",
            description="Move the mouse cursor to specific screen coordinates (no click).",
            args_model=MoveMouseArgs,
            risk_level=RiskLevel.LOW,
            permission_level=PermissionLevel.USER,
            handler=move_mouse_tool,
        )
    )
    registry.register(
        ToolDefinition(
            name="type_text",
            description=(
                "Type text at the current keyboard focus. Requires confirm=true. This types "
                "wherever the OS focus currently is -- make sure the right window/field is "
                "focused first."
            ),
            args_model=TypeTextArgs,
            risk_level=RiskLevel.CRITICAL,
            permission_level=PermissionLevel.CONFIRM,
            handler=type_text_tool,
        )
    )
    registry.register(
        ToolDefinition(
            name="press_key",
            description="Press a key or key combo (e.g. 'enter', 'ctrl+c'). Requires confirm=true.",
            args_model=PressKeyArgs,
            risk_level=RiskLevel.HIGH,
            permission_level=PermissionLevel.CONFIRM,
            handler=press_key_tool,
        )
    )
    registry.register(
        ToolDefinition(
            name="scroll",
            description="Scroll the mouse wheel, optionally at specific coordinates.",
            args_model=ScrollArgs,
            risk_level=RiskLevel.MEDIUM,
            permission_level=PermissionLevel.USER,
            handler=scroll_tool,
        )
    )
    registry.register(
        ToolDefinition(
            name="focus_window",
            description=(
                "Bring the first window whose title contains the given text to the foreground. "
                "If multiple windows could match (e.g. several browser/editor windows), use the "
                "most specific substring you can -- a vague match like 'Notepad' can bring an "
                "unrelated, already-open window forward instead of the one you meant. Verify with "
                "identify_application after focusing before clicking/typing."
            ),
            args_model=FocusWindowArgs,
            risk_level=RiskLevel.LOW,
            permission_level=PermissionLevel.USER,
            handler=focus_window_tool,
        )
    )
