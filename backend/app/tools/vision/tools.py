"""Screen-vision tools: take_screenshot, analyze_screen, detect_text,
identify_application.

Raw image bytes are never put into a tool result -- the orchestrating agent
is a text model and can't do anything useful with an inline base64 blob
except bloat its own context. `analyze_screen`/`detect_text` capture a
screenshot internally and return only the resulting text; `take_screenshot`
either saves to the file workspace (if asked) or just confirms capture with
dimensions.
"""
from __future__ import annotations

import asyncio

from pydantic import BaseModel, Field

from app.ai.router import get_ai_router
from app.core.config import get_settings
from app.security.validators import PathSecurityError, resolve_safe_path
from app.tools.base import PermissionLevel, RiskLevel, ToolDefinition, ToolResult
from app.tools.registry import ToolRegistry
from app.vision.ocr import OCRUnavailableError, extract_text, is_ocr_available
from app.vision.screen_parser import identify_active_application
from app.vision.screenshot import NoSuchMonitorError, capture_screenshot
from app.vision.vision_analysis import VisionUnavailableError, analyze_image


class TakeScreenshotArgs(BaseModel):
    monitor_index: int = Field(default=1, description="1 = primary monitor, 2 = secondary, etc.")
    save_as: str | None = Field(
        default=None, description="If given, save the screenshot as this filename in the workspace"
    )


async def take_screenshot(args: TakeScreenshotArgs) -> ToolResult:
    try:
        shot = await asyncio.to_thread(capture_screenshot, args.monitor_index)
    except NoSuchMonitorError as exc:
        return ToolResult.fail("NO_SUCH_MONITOR", str(exc))

    if not args.save_as:
        return ToolResult.ok(
            data={"width": shot.width, "height": shot.height, "monitor_index": shot.monitor_index}
        )

    try:
        path = resolve_safe_path(args.save_as, get_settings())
    except PathSecurityError as exc:
        return ToolResult.fail("PATH_DENIED", str(exc))

    def _write() -> None:
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(shot.png_bytes)

    await asyncio.to_thread(_write)
    return ToolResult.ok(
        data={"saved_path": str(path), "width": shot.width, "height": shot.height}
    )


class AnalyzeScreenArgs(BaseModel):
    prompt: str | None = Field(
        default=None, description="What to look for; defaults to a general description"
    )
    monitor_index: int = Field(default=1)


async def analyze_screen(args: AnalyzeScreenArgs) -> ToolResult:
    settings = get_settings()
    try:
        shot = await asyncio.to_thread(capture_screenshot, args.monitor_index, 1280)
    except NoSuchMonitorError as exc:
        return ToolResult.fail("NO_SUCH_MONITOR", str(exc))

    try:
        description = await analyze_image(get_ai_router(), settings, shot.png_bytes, args.prompt)
    except VisionUnavailableError as exc:
        return ToolResult.fail("VISION_UNAVAILABLE", str(exc))

    return ToolResult.ok(data={"description": description, "width": shot.width, "height": shot.height})


class DetectTextArgs(BaseModel):
    monitor_index: int = Field(default=1)


async def detect_text(args: DetectTextArgs) -> ToolResult:
    if not is_ocr_available():
        return ToolResult.fail(
            "OCR_UNAVAILABLE", "Tesseract OCR is not installed/found on this machine."
        )

    try:
        shot = await asyncio.to_thread(capture_screenshot, args.monitor_index)
    except NoSuchMonitorError as exc:
        return ToolResult.fail("NO_SUCH_MONITOR", str(exc))

    try:
        text = await asyncio.to_thread(extract_text, shot.png_bytes)
    except OCRUnavailableError as exc:
        return ToolResult.fail("OCR_UNAVAILABLE", str(exc))

    return ToolResult.ok(data={"text": text})


class NoArgs(BaseModel):
    pass


async def identify_application(_: NoArgs) -> ToolResult:
    result = await asyncio.to_thread(identify_active_application)
    if not result.supported:
        return ToolResult.fail("UNSUPPORTED", result.note or "Not supported on this platform")
    return ToolResult.ok(data=result.active_window.model_dump() if result.active_window else {})


def register(registry: ToolRegistry) -> None:
    registry.register(
        ToolDefinition(
            name="take_screenshot",
            description=(
                "Capture a screenshot. Optionally save it to a file; otherwise just "
                "confirms capture with dimensions."
            ),
            args_model=TakeScreenshotArgs,
            risk_level=RiskLevel.MEDIUM,
            permission_level=PermissionLevel.USER,
            timeout_seconds=10.0,
            handler=take_screenshot,
        )
    )
    registry.register(
        ToolDefinition(
            name="analyze_screen",
            description="Capture the screen and describe what's on it using a vision model.",
            args_model=AnalyzeScreenArgs,
            risk_level=RiskLevel.MEDIUM,
            permission_level=PermissionLevel.USER,
            timeout_seconds=90.0,
            handler=analyze_screen,
        )
    )
    registry.register(
        ToolDefinition(
            name="detect_text",
            description="Capture the screen and extract visible text via OCR.",
            args_model=DetectTextArgs,
            risk_level=RiskLevel.MEDIUM,
            permission_level=PermissionLevel.USER,
            timeout_seconds=15.0,
            handler=detect_text,
        )
    )
    registry.register(
        ToolDefinition(
            name="identify_application",
            description="Identify the currently focused/foreground application window.",
            args_model=NoArgs,
            risk_level=RiskLevel.LOW,
            permission_level=PermissionLevel.SAFE,
            handler=identify_application,
        )
    )
