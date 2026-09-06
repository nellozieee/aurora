from __future__ import annotations

from app.ai.openai_compatible import OpenAICompatibleProvider
from app.core.config import Settings


class OpenAIProvider(OpenAICompatibleProvider):
    def __init__(self, settings: Settings) -> None:
        super().__init__(
            name="openai",
            api_key=settings.openai_api_key,
            base_url=settings.openai_base_url,
            default_model=settings.openai_model,
        )
