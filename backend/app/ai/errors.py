"""Helpers for turning low-level httpx exceptions into readable error text.

httpx exceptions (e.g. ReadTimeout, ConnectError) frequently have an empty
`str()`, so a plain f"{exc}" produces an unhelpful "request failed: " message.
"""
from __future__ import annotations

import httpx


def describe_httpx_error(exc: httpx.HTTPError) -> str:
    message = str(exc)
    return message if message else type(exc).__name__
