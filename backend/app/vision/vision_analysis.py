"""Vision-model analysis of an image, via the AI provider abstraction."""
from __future__ import annotations

from app.ai.router import AIRouter
from app.ai.schemas import ProviderRequestError, ProviderUnavailableError
from app.core.config import Settings


class VisionUnavailableError(Exception):
    pass


DEFAULT_SCREEN_PROMPT = (
    "Describe what is currently visible on this screen: the active application, "
    "visible window(s), and any notable UI elements or content. Be factual and "
    "concise -- describe only what you can actually see."
)


async def analyze_image(
    ai_router: AIRouter, settings: Settings, image_bytes: bytes, prompt: str | None = None
) -> str:
    try:
        provider = ai_router.get_provider(settings.vision_provider)
        return await provider.vision(image_bytes, prompt or DEFAULT_SCREEN_PROMPT, model=settings.vision_model)
    except NotImplementedError as exc:
        raise VisionUnavailableError(
            f"{settings.vision_provider} does not implement vision analysis"
        ) from exc
    except (ProviderUnavailableError, ProviderRequestError) as exc:
        raise VisionUnavailableError(str(exc)) from exc
