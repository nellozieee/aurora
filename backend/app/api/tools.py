"""Tool listing + manual execution API.

Manual execution here goes through the exact same `ToolRouter` the chat/agent
pipeline will use in later phases -- there is no separate, less-validated
path for the frontend Tools page.
"""
from __future__ import annotations

from fastapi import APIRouter, Depends
from pydantic import BaseModel

from app.tools.base import ToolResult
from app.tools.registry import ToolRegistry, get_tool_registry
from app.tools.router import ToolRouter

router = APIRouter(prefix="/api/tools", tags=["tools"])


class ToolSummary(BaseModel):
    name: str
    description: str
    risk_level: str
    permission_level: str
    timeout_seconds: float
    input_schema: dict


class ToolExecuteRequest(BaseModel):
    arguments: dict = {}


def get_tool_router(registry: ToolRegistry = Depends(get_tool_registry)) -> ToolRouter:
    return ToolRouter(registry)


@router.get("", response_model=list[ToolSummary])
async def list_tools(registry: ToolRegistry = Depends(get_tool_registry)) -> list[ToolSummary]:
    return [
        ToolSummary(
            name=t.name,
            description=t.description,
            risk_level=t.risk_level.value,
            permission_level=t.permission_level.value,
            timeout_seconds=t.timeout_seconds,
            input_schema=t.input_schema(),
        )
        for t in registry.list_all()
    ]


@router.post("/{tool_name}/execute", response_model=ToolResult)
async def execute_tool(
    tool_name: str,
    request: ToolExecuteRequest,
    tool_router: ToolRouter = Depends(get_tool_router),
) -> ToolResult:
    return await tool_router.execute(tool_name, request.arguments)
