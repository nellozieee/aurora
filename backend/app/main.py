"""Aurora backend entrypoint."""
from __future__ import annotations

from collections.abc import AsyncGenerator
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.agents.registry import list_agents
from app.api import agents as agents_api
from app.api import automations as automations_api
from app.api import chat as chat_api
from app.api import memory as memory_api
from app.api import system as system_api
from app.api import tasks as tasks_api
from app.api import tools as tools_api
from app.api import voice as voice_api
from app.automation.scheduler import start_scheduler, stop_scheduler
from app.core.config import get_settings
from app.core.rate_limit import RateLimitMiddleware
from app.database.database import check_database_connection, dispose_engine
from app.database.redis_client import check_redis_connection, dispose_redis
from app.tools.bootstrap import register_all_tools
from app.utils.logging import configure_logging, get_logger

configure_logging()
logger = get_logger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncGenerator[None, None]:
    settings = get_settings()
    logger.info("startup.begin", app_name=settings.app_name, env=settings.app_env)

    db_ok = await check_database_connection()
    logger.info("startup.database", status="online" if db_ok else "unreachable")

    redis_ok = await check_redis_connection()
    logger.info("startup.redis", status="online" if redis_ok else "unreachable")

    registry = register_all_tools()
    logger.info("startup.tools", count=len(registry.list_all()))

    # Agents are registered as a static module-level dict (app/agents/registry.py),
    # already populated by the time this import resolves -- this just makes that
    # step visible in the startup sequence per its own place in the checklist.
    logger.info("startup.agents", count=len(list_agents()))

    start_scheduler()
    logger.info("startup.scheduler")

    logger.info("startup.complete")
    yield

    logger.info("shutdown.begin")
    await stop_scheduler()
    await dispose_engine()
    await dispose_redis()
    logger.info("shutdown.complete")


def create_app() -> FastAPI:
    settings = get_settings()

    app = FastAPI(
        title=f"{settings.app_name} API",
        description="Modular personal AI assistant backend.",
        version="0.1.0",
        lifespan=lifespan,
    )

    cors_kwargs: dict = {
        "allow_origins": settings.cors_allowed_origins,
        "allow_credentials": True,
        "allow_methods": ["*"],
        "allow_headers": ["*"],
    }
    if settings.app_env == "development":
        # Vite picks the next free port if its default is taken, so in
        # development tolerate any localhost port rather than one hardcoded
        # value; production must rely on the explicit allowlist above.
        cors_kwargs["allow_origin_regex"] = r"http://(localhost|127\.0\.0\.1):\d+"

    # Middleware order: Starlette makes the *last*-added middleware the
    # outermost layer, so CORS (added last) wraps the rate limiter -- every
    # response, including a 429, still gets correct CORS headers.
    app.add_middleware(RateLimitMiddleware)
    app.add_middleware(CORSMiddleware, **cors_kwargs)

    app.include_router(system_api.router)
    app.include_router(chat_api.router)
    app.include_router(memory_api.router)
    app.include_router(tools_api.router)
    app.include_router(agents_api.router)
    app.include_router(voice_api.router)
    app.include_router(automations_api.router)
    app.include_router(tasks_api.router)

    return app


app = create_app()
