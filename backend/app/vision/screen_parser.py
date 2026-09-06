"""Combines screenshot capture with active-window identification."""
from __future__ import annotations

from pydantic import BaseModel

from app.system import get_platform_adapter
from app.system.base import ActiveWindowInfo, ActiveWindowUnsupportedError


class ActiveApplicationResult(BaseModel):
    active_window: ActiveWindowInfo | None
    supported: bool
    note: str | None = None


def identify_active_application() -> ActiveApplicationResult:
    adapter = get_platform_adapter()
    try:
        window = adapter.get_active_window()
        return ActiveApplicationResult(active_window=window, supported=True)
    except ActiveWindowUnsupportedError as exc:
        return ActiveApplicationResult(active_window=None, supported=False, note=str(exc))
