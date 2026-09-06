"""Registers every built-in tool at application startup."""
from __future__ import annotations

from app.tools.automation import tools as automation_tools
from app.tools.computer import tools as computer_control_tools
from app.tools.files import tools as file_tools
from app.tools.registry import ToolRegistry, get_tool_registry
from app.tools.system import tools as system_tools
from app.tools.terminal import tools as terminal_tools
from app.tools.vision import tools as vision_tools
from app.tools.web import tools as web_tools


def register_all_tools(registry: ToolRegistry | None = None) -> ToolRegistry:
    registry = registry or get_tool_registry()
    file_tools.register(registry)
    web_tools.register(registry)
    system_tools.register(registry)
    terminal_tools.register(registry)
    vision_tools.register(registry)
    computer_control_tools.register(registry)
    automation_tools.register(registry)
    return registry
