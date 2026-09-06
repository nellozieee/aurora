"""Desktop toast notifications (Windows via win11toast).

Uses `notify()`, which fires the OS toast and returns immediately (unlike
some alternatives that block until the toast is dismissed) -- appropriate
for an async backend.
"""
from __future__ import annotations

import asyncio
import platform

from app.notifications.base import NotificationProvider, NotificationResult


class DesktopNotificationProvider(NotificationProvider):
    name = "desktop"

    async def is_available(self) -> bool:
        return platform.system() == "Windows"

    async def send(self, title: str, message: str) -> NotificationResult:
        if platform.system() != "Windows":
            return NotificationResult(
                success=False, provider=self.name, error="Desktop notifications only implemented on Windows"
            )

        try:
            from win11toast import notify

            await asyncio.to_thread(notify, title, message, app_id="Aurora")
        except Exception as exc:
            return NotificationResult(success=False, provider=self.name, error=str(exc))
        return NotificationResult(success=True, provider=self.name)
