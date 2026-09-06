"""The centralized permission engine (spec section 33).

Section 33 is explicit: "The permission engine must be centralized. Do not
implement permission checks independently inside random tools." Before this,
five tool handlers (click, double_click, type_text, press_key, delete_file)
each duplicated their own `if not args.confirm: return fail(...)` check.
`enforce()` is now the *only* place that decision is made -- `ToolRouter`
calls it before invoking any handler, and the handlers no longer gate on
`confirm` themselves (the `confirm` field stays on their args models purely
so the tool's JSON schema tells the calling model the argument exists).
"""
from __future__ import annotations

from app.tools.base import PermissionLevel, ToolDefinition


class PermissionDenied(Exception):
    def __init__(self, code: str, message: str) -> None:
        super().__init__(message)
        self.code = code
        self.message = message


def enforce(tool: ToolDefinition, arguments: dict) -> None:
    """Raise `PermissionDenied` if `tool` may not run with `arguments` yet.

    SAFE/USER-level tools always pass. CONFIRM-level tools (currently every
    HIGH/CRITICAL-risk tool) require the caller to have already passed
    `confirm=true` -- which the agent only does after the user has approved
    the action in the conversation, or a direct API caller sets explicitly.
    """
    if tool.permission_level != PermissionLevel.CONFIRM:
        return
    if arguments.get("confirm") is True:
        return
    raise PermissionDenied(
        "PERMISSION_REQUIRED",
        f"'{tool.name}' is a {tool.risk_level.value}-risk action and requires explicit "
        "confirmation. Ask the user to confirm first, then call this tool again with "
        "confirm=true.",
    )


def permission_status(tool: ToolDefinition, *, denied: bool) -> str:
    """The audit-log value describing how permission was resolved for this call."""
    if tool.permission_level != PermissionLevel.CONFIRM:
        return "not_required"
    return "denied" if denied else "granted"
