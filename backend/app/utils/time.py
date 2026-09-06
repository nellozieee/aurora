"""Shared time helper.

The DB stores naive datetimes (implicitly UTC) throughout this codebase;
`datetime.utcnow()` produces the same naive-UTC value but is deprecated as
of Python 3.12+. This is the replacement -- same semantics, not deprecated.
"""
from __future__ import annotations

from datetime import UTC, datetime


def utc_now() -> datetime:
    return datetime.now(UTC).replace(tzinfo=None)
