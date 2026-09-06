"""Structured logging configuration.

Every log record can carry a request_id and other correlation fields so
individual requests can be traced across subsystems (see docs/architecture.md).
"""
from __future__ import annotations

import logging
import sys
from typing import cast

import structlog

from app.core.config import get_settings
from app.security.secrets import redact_value


def _redact_secrets_processor(logger: object, method_name: str, event_dict: dict) -> dict:
    """Redact any configured secret value out of every log record (section 64).

    Applied to every log call in the process, not just tool-related ones --
    a stray provider exception, an httpx error, or a raw DB error can all
    otherwise embed an API key or connection-string password in the message.
    """
    # redact_value's signature is intentionally `object -> object` (it
    # recurses through arbitrary values) -- a dict in always produces a
    # dict out, per its own implementation, which mypy can't see through.
    return cast(dict, redact_value(event_dict))


def configure_logging() -> None:
    settings = get_settings()
    level = getattr(logging, settings.log_level.upper(), logging.INFO)

    logging.basicConfig(format="%(message)s", stream=sys.stdout, level=level)

    shared_processors: list = [
        structlog.contextvars.merge_contextvars,
        structlog.processors.add_log_level,
        structlog.processors.TimeStamper(fmt="iso"),
        structlog.processors.StackInfoRenderer(),
        _redact_secrets_processor,
    ]

    renderer: structlog.types.Processor
    if settings.log_json:
        renderer = structlog.processors.JSONRenderer()
    else:
        renderer = structlog.dev.ConsoleRenderer()

    structlog.configure(
        processors=shared_processors + [renderer],
        wrapper_class=structlog.make_filtering_bound_logger(level),
        context_class=dict,
        logger_factory=structlog.PrintLoggerFactory(),
        cache_logger_on_first_use=True,
    )


def get_logger(name: str) -> structlog.stdlib.BoundLogger:
    return structlog.get_logger(name)
