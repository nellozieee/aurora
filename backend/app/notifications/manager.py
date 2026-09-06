"""Aggregates all notification providers behind one `send()` call.

This is what tools and the automation executor use -- they never see
individual providers or their credentials.
"""
from __future__ import annotations

from functools import lru_cache

from app.core.config import Settings, get_settings
from app.notifications.base import NotificationProvider, NotificationResult
from app.notifications.desktop import DesktopNotificationProvider
from app.notifications.telegram import TelegramNotificationProvider
from app.utils.logging import get_logger

logger = get_logger(__name__)


class NotificationManager:
    def __init__(self, settings: Settings) -> None:
        self._providers: list[NotificationProvider] = [
            DesktopNotificationProvider(),
            TelegramNotificationProvider(settings),
        ]

    async def send(self, title: str, message: str) -> list[NotificationResult]:
        """Send to every currently-available provider. Never raises -- a
        notification failing is logged, not propagated as an error to
        whatever triggered it (a reminder firing shouldn't fail the
        automation just because, say, Telegram is unreachable)."""
        results: list[NotificationResult] = []
        for provider in self._providers:
            if not await provider.is_available():
                continue
            try:
                result = await provider.send(title, message)
            except Exception as exc:  # defensive: notifications must never crash the caller
                result = NotificationResult(success=False, provider=provider.name, error=str(exc))
            if not result.success:
                logger.warning("notification.failed", provider=result.provider, error=result.error)
            results.append(result)
        return results

    async def provider_statuses(self) -> dict[str, str]:
        statuses = {}
        for provider in self._providers:
            statuses[provider.name] = "online" if await provider.is_available() else "not_configured"
        return statuses


@lru_cache
def get_notification_manager() -> NotificationManager:
    return NotificationManager(get_settings())
