"""A minimal in-process rate limiter (spec section 114: "missing rate limits").

This is a single-operator local assistant, not a public multi-tenant
service -- the realistic threat isn't an external attacker, it's a buggy
frontend retry loop or a runaway script on the LAN hammering an expensive
endpoint (chat, code execution). A simple fixed-window counter per client
IP is proportionate to that; it is deliberately not a distributed/Redis-
backed limiter, since this process is the only one ever serving traffic.
"""
from __future__ import annotations

import time
from collections import defaultdict

from fastapi import Request
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.responses import JSONResponse

from app.core.config import get_settings


class RateLimitMiddleware(BaseHTTPMiddleware):
    def __init__(self, app) -> None:
        super().__init__(app)
        self._window_seconds = 60.0
        self._request_times: dict[str, list[float]] = defaultdict(list)

    async def dispatch(self, request: Request, call_next):
        settings = get_settings()
        if not settings.rate_limit_enabled:
            return await call_next(request)

        client_key = request.client.host if request.client else "unknown"
        now = time.monotonic()
        window_start = now - self._window_seconds

        recent = [t for t in self._request_times[client_key] if t > window_start]
        if len(recent) >= settings.rate_limit_requests_per_minute:
            return JSONResponse(
                status_code=429,
                content={
                    "detail": (
                        f"Rate limit exceeded: max {settings.rate_limit_requests_per_minute} "
                        "requests per minute. Try again shortly."
                    )
                },
            )

        recent.append(now)
        self._request_times[client_key] = recent
        return await call_next(request)
