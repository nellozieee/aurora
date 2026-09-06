"""Screen capture.

Screenshots are only ever taken in direct response to an explicit tool call
(itself only reachable from an active, user-initiated agent turn) -- nothing
in this module runs on a timer or in the background, and captured images are
returned in-memory rather than written anywhere persistent.
"""
from __future__ import annotations

import io

from PIL import Image
from pydantic import BaseModel


class ScreenshotResult(BaseModel):
    model_config = {"arbitrary_types_allowed": True}

    png_bytes: bytes
    width: int
    height: int
    monitor_index: int


class NoSuchMonitorError(Exception):
    pass


def list_monitors() -> list[dict]:
    import mss

    with mss.mss() as sct:
        # index 0 is "all monitors combined" in mss's convention; 1..N are
        # the individual physical monitors.
        return [
            {"index": i, "width": m["width"], "height": m["height"]}
            for i, m in enumerate(sct.monitors)
        ]


def capture_screenshot(monitor_index: int = 1, max_width: int | None = None) -> ScreenshotResult:
    """Capture at full resolution by default -- OCR accuracy degrades on
    downscaled text. Pass `max_width` to shrink the image (e.g. before
    sending it to a vision model, where payload size/cost matters more than
    pixel-perfect text)."""
    import mss

    with mss.mss() as sct:
        if monitor_index < 0 or monitor_index >= len(sct.monitors):
            raise NoSuchMonitorError(
                f"No monitor at index {monitor_index}; available: 0-{len(sct.monitors) - 1}"
            )
        raw = sct.grab(sct.monitors[monitor_index])
        image = Image.frombytes("RGB", raw.size, raw.rgb)

    if max_width is not None and image.width > max_width:
        ratio = max_width / image.width
        image = image.resize((max_width, round(image.height * ratio)))

    buffer = io.BytesIO()
    image.save(buffer, format="PNG")
    return ScreenshotResult(
        png_bytes=buffer.getvalue(),
        width=image.width,
        height=image.height,
        monitor_index=monitor_index,
    )
