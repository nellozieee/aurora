"""System status / health-check endpoints."""
from __future__ import annotations

import time

from fastapi import APIRouter, Depends

from app.ai.router import AIRouter, get_ai_router
from app.core.config import get_settings
from app.database.database import check_database_connection
from app.database.redis_client import check_redis_connection
from app.notifications.manager import NotificationManager, get_notification_manager
from app.voice.stt import get_stt_provider
from app.voice.tts import get_tts_provider

router = APIRouter(prefix="/api/system", tags=["system"])

_START_TIME = time.monotonic()


@router.get("/status")
async def system_status(
    ai_router: AIRouter = Depends(get_ai_router),
    notification_manager: NotificationManager = Depends(get_notification_manager),
) -> dict:
    """Report the real, currently-observed status of each subsystem.

    Subsystems that have not been implemented yet (voice, vision, Telegram,
    ...) are intentionally omitted rather than reported with a fabricated
    status -- they are added to this response as each subsystem comes online
    in later phases.
    """
    settings = get_settings()

    db_ok = await check_database_connection()
    redis_ok = await check_redis_connection()
    ai_statuses = await ai_router.provider_statuses()
    notification_statuses = await notification_manager.provider_statuses()

    if settings.voice_enabled:
        stt_status = "online" if await get_stt_provider().is_available() else "error"
        tts_status = "online" if await get_tts_provider().is_available() else "error"
    else:
        stt_status = "disabled"
        tts_status = "disabled"

    return {
        "assistant_name": settings.app_name,
        "environment": settings.app_env,
        "uptime_seconds": round(time.monotonic() - _START_TIME, 2),
        "subsystems": {
            "backend": "online",
            "database": "online" if db_ok else "error",
            "redis": "online" if redis_ok else "error",
            **{f"ai.{name}": status for name, status in ai_statuses.items()},
            "voice.stt": stt_status,
            "voice.tts": tts_status,
            **{f"notifications.{name}": status for name, status in notification_statuses.items()},
        },
    }


@router.get("/health")
async def health() -> dict:
    """Liveness probe. Always returns 200 while the process is running."""
    return {"status": "ok"}
