"""Telegram notifications via the Bot API.

The bot token/chat ID live only in backend settings -- this provider is the
only thing that ever touches them; callers (tools, the automation executor)
only ever see `notification_manager.send(...)`.
"""
from __future__ import annotations

import httpx

from app.core.config import Settings
from app.notifications.base import NotificationProvider, NotificationResult


class TelegramNotificationProvider(NotificationProvider):
    name = "telegram"

    def __init__(self, settings: Settings) -> None:
        self._token = settings.telegram_bot_token
        self._chat_id = settings.telegram_chat_id

    async def is_available(self) -> bool:
        return bool(self._token and self._chat_id)

    async def send(self, title: str, message: str) -> NotificationResult:
        if not (self._token and self._chat_id):
            return NotificationResult(
                success=False, provider=self.name, error="Telegram is not configured (missing bot token/chat id)"
            )

        text = f"*{title}*\n{message}" if title else message
        try:
            async with httpx.AsyncClient(timeout=10.0) as client:
                response = await client.post(
                    f"https://api.telegram.org/bot{self._token}/sendMessage",
                    json={"chat_id": self._chat_id, "text": text, "parse_mode": "Markdown"},
                )
        except httpx.HTTPError as exc:
            return NotificationResult(success=False, provider=self.name, error=f"Request failed: {exc}")

        if response.status_code >= 400:
            error = f"Telegram API returned {response.status_code}: {response.text[:300]}"
            return NotificationResult(success=False, provider=self.name, error=error)
        return NotificationResult(success=True, provider=self.name)
