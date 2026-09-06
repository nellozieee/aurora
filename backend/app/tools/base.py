"""Tool registry primitives.

Every tool the AI can call is registered as a `ToolDefinition`. The LLM never
gets raw access to Python functions, shell commands, or the filesystem --
only to whatever is registered here, each with a validated input schema, an
explicit risk classification, and a timeout.
"""
from __future__ import annotations

from collections.abc import Awaitable, Callable
from enum import StrEnum
from typing import Any

from pydantic import BaseModel


class RiskLevel(StrEnum):
    SAFE = "safe"
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    CRITICAL = "critical"


class PermissionLevel(StrEnum):
    """Who/what may invoke this tool without extra confirmation.

    The full confirmation/permission engine lands in a later phase; today,
    HIGH/CRITICAL-risk tools additionally enforce their own explicit
    `confirm=True` argument rather than running unchecked in the meantime.
    """

    SAFE = "safe"
    USER = "user"
    CONFIRM = "confirm"


class ToolError(BaseModel):
    code: str
    message: str


class ToolResult(BaseModel):
    success: bool
    data: Any = None
    error: ToolError | None = None
    metadata: dict[str, Any] = {}

    @staticmethod
    def ok(data: Any = None, **metadata: Any) -> ToolResult:
        return ToolResult(success=True, data=data, metadata=metadata)

    @staticmethod
    def fail(code: str, message: str, **metadata: Any) -> ToolResult:
        return ToolResult(success=False, error=ToolError(code=code, message=message), metadata=metadata)


# A registry of tools is inherently heterogeneous: each handler actually
# accepts its own specific args model (e.g. `Callable[[ClickArgs], ...]`),
# not the base `BaseModel`. Callable parameter types are contravariant, so
# mypy correctly considers a narrower-arg callable an invalid match for a
# `Callable[[BaseModel], ...]` slot -- typing this as `Callable[..., ...]`
# is the honest signature for a registry whose real safety comes from
# `ToolRouter.execute()` validating raw arguments against each tool's own
# `args_model` before ever calling its handler, not from static handler typing.
ToolHandler = Callable[..., Awaitable[ToolResult]]


class ToolDefinition(BaseModel):
    model_config = {"arbitrary_types_allowed": True}

    name: str
    description: str
    args_model: type[BaseModel]
    risk_level: RiskLevel
    permission_level: PermissionLevel
    timeout_seconds: float = 15.0
    handler: ToolHandler

    def input_schema(self) -> dict[str, Any]:
        return self.args_model.model_json_schema()
