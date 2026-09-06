"""System-information and application-control tools.

Application launch/close go through the platform adapter's fixed registry --
the model supplies a friendly name only, never a raw command.
"""
from __future__ import annotations

import asyncio

from pydantic import BaseModel, Field

from app.system import get_platform_adapter
from app.system.base import AppLaunchError
from app.tools.base import PermissionLevel, RiskLevel, ToolDefinition, ToolResult
from app.tools.registry import ToolRegistry


class NoArgs(BaseModel):
    pass


async def get_system_info(_: NoArgs) -> ToolResult:
    adapter = get_platform_adapter()
    info = await asyncio.to_thread(adapter.get_system_info)
    return ToolResult.ok(data=info.model_dump())


class ListProcessesArgs(BaseModel):
    limit: int = Field(default=50, ge=1, le=500)


async def list_processes(args: ListProcessesArgs) -> ToolResult:
    adapter = get_platform_adapter()
    processes = await asyncio.to_thread(adapter.list_processes, args.limit)
    return ToolResult.ok(
        data={"processes": [p.model_dump() for p in processes]}, count=len(processes)
    )


class OpenApplicationArgs(BaseModel):
    name: str = Field(description="Friendly application name, e.g. 'notepad', 'vscode', 'chrome'")


async def open_application(args: OpenApplicationArgs) -> ToolResult:
    adapter = get_platform_adapter()
    try:
        pid = await asyncio.to_thread(adapter.launch_application, args.name)
    except AppLaunchError as exc:
        return ToolResult.fail("APP_LAUNCH_FAILED", str(exc))
    return ToolResult.ok(data={"name": args.name, "pid": pid})


class CloseApplicationArgs(BaseModel):
    name: str = Field(description="Process name (or substring) to terminate")


async def close_application(args: CloseApplicationArgs) -> ToolResult:
    adapter = get_platform_adapter()
    closed = await asyncio.to_thread(adapter.close_application, args.name)
    if closed == 0:
        return ToolResult.fail("NOT_FOUND", f"No running process matched '{args.name}'")
    return ToolResult.ok(data={"name": args.name, "processes_closed": closed})


def register(registry: ToolRegistry) -> None:
    registry.register(
        ToolDefinition(
            name="get_system_info",
            description="Get OS, CPU, memory, and disk information for this machine.",
            args_model=NoArgs,
            risk_level=RiskLevel.SAFE,
            permission_level=PermissionLevel.SAFE,
            handler=get_system_info,
        )
    )
    registry.register(
        ToolDefinition(
            name="list_processes",
            description="List currently running processes (read-only).",
            args_model=ListProcessesArgs,
            risk_level=RiskLevel.LOW,
            permission_level=PermissionLevel.USER,
            handler=list_processes,
        )
    )
    registry.register(
        ToolDefinition(
            name="open_application",
            description="Launch a registered desktop application by friendly name.",
            args_model=OpenApplicationArgs,
            risk_level=RiskLevel.LOW,
            permission_level=PermissionLevel.USER,
            handler=open_application,
        )
    )
    registry.register(
        ToolDefinition(
            name="close_application",
            description="Terminate running process(es) matching a name.",
            args_model=CloseApplicationArgs,
            risk_level=RiskLevel.MEDIUM,
            permission_level=PermissionLevel.USER,
            handler=close_application,
        )
    )
