"""Notification provider abstraction.

Adding a new channel (email, Discord, mobile push) means implementing this
interface and registering it in `manager.py` -- nothing else in the system
(automation executor, tools) needs to change.
"""
from __future__ import annotations

from abc import ABC, abstractmethod

from pydantic import BaseModel


class NotificationResult(BaseModel):
    success: bool
    provider: str
    error: str | None = None


class NotificationProvider(ABC):
    name: str

    @abstractmethod
    async def is_available(self) -> bool: ...

    @abstractmethod
    async def send(self, title: str, message: str) -> NotificationResult: ...
