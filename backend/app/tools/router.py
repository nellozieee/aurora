"""Validates and executes tool calls.

This is the only path by which a tool handler ever runs. It:
  1. Looks the tool up in the registry (unknown tool -> failed ToolResult).
  2. Validates raw arguments against the tool's pydantic args model (never
     trusts model-generated arguments directly).
  3. Runs the handler under a timeout.
  4. Converts any exception into a structured, non-throwing ToolResult.
"""
from __future__ import annotations

import asyncio
import hashlib
import json
import time
from typing import cast

import pydantic

from app.security import permissions
from app.security.secrets import redact, redact_value
from app.tools.base import ToolResult
from app.tools.registry import ToolRegistry
from app.utils.logging import get_logger

logger = get_logger(__name__)


def arguments_hash(arguments: dict) -> str:
    """A stable, non-reversible fingerprint of tool arguments for audit rows.

    Hashed rather than stored raw so audit logs never carry sensitive
    argument values (e.g. reminder message text, file contents) -- only
    enough to correlate repeated/identical calls.
    """
    redacted = redact_value(arguments)
    canonical = json.dumps(redacted, sort_keys=True, default=str)
    return hashlib.sha256(canonical.encode("utf-8")).hexdigest()


class ToolRouter:
    def __init__(self, registry: ToolRegistry) -> None:
        self._registry = registry

    async def execute(self, name: str, arguments: dict) -> ToolResult:
        start = time.monotonic()
        tool = self._registry.get(name)
        if tool is None:
            return ToolResult.fail("UNKNOWN_TOOL", f"No tool registered with name '{name}'")

        try:
            permissions.enforce(tool, arguments)
        except permissions.PermissionDenied as exc:
            logger.info("tool.permission_denied", tool=name, risk_level=tool.risk_level.value)
            return ToolResult.fail(exc.code, exc.message, permission_status="denied")

        try:
            parsed_args = tool.args_model.model_validate(arguments)
        except pydantic.ValidationError as exc:
            return ToolResult.fail("INVALID_ARGUMENTS", redact(str(exc)))

        logger.info("tool.started", tool=name, risk_level=tool.risk_level.value)
        logger.debug("tool.arguments", tool=name, arguments=arguments)
        try:
            result = await asyncio.wait_for(tool.handler(parsed_args), timeout=tool.timeout_seconds)
        except TimeoutError:
            result = ToolResult.fail(
                "TIMEOUT", f"Tool '{name}' did not complete within {tool.timeout_seconds}s"
            )
        except Exception as exc:  # a tool must never crash the caller
            logger.warning("tool.exception", tool=name, error=redact(str(exc)))
            result = ToolResult.fail("TOOL_ERROR", redact(str(exc)))

        duration = round(time.monotonic() - start, 3)
        logger.info("tool.completed", tool=name, success=result.success, duration=duration)
        # Redact defensively: never let a secret configured for an external
        # provider (API key, DB password, bot token) reach the AI model or
        # the frontend inside a tool's own output (section 64).
        result = ToolResult(
            success=result.success,
            data=redact_value(result.data),
            error=result.error.model_copy(update={"message": redact(result.error.message)})
            if result.error
            else None,
            # redact_value's signature is `object -> object` (it recurses
            # through arbitrary values); a dict in always produces a dict out.
            metadata=cast(dict, redact_value(result.metadata)),
        )
        return result.model_copy(
            update={
                "metadata": {
                    **result.metadata,
                    "duration_seconds": duration,
                    "permission_status": permissions.permission_status(tool, denied=False),
                }
            }
        )
