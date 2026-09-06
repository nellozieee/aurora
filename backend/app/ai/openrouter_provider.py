from __future__ import annotations

from app.ai.openai_compatible import OpenAICompatibleProvider
from app.core.config import Settings


class OpenRouterProvider(OpenAICompatibleProvider):
    def __init__(self, settings: Settings) -> None:
        super().__init__(
            name="openrouter",
            api_key=settings.openrouter_api_key,
            base_url=settings.openrouter_base_url,
            default_model=settings.openrouter_model or "openrouter/auto",
            extra_headers={
                "HTTP-Referer": "https://github.com/aurora-assistant",
                "X-Title": settings.app_name,
            },
        )
