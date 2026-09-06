"""Platform adapter selection."""
from __future__ import annotations

import platform
from functools import lru_cache

from app.system.base import PlatformAdapter


@lru_cache
def get_platform_adapter() -> PlatformAdapter:
    system = platform.system()
    if system == "Windows":
        from app.system.windows import WindowsAdapter

        return WindowsAdapter()
    if system == "Linux":
        from app.system.linux import LinuxAdapter

        return LinuxAdapter()
    if system == "Darwin":
        from app.system.macos import MacOSAdapter

        return MacOSAdapter()
    raise RuntimeError(f"Unsupported platform: {system}")
