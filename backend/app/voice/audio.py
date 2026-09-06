"""Temp-file handling for uploaded audio clips."""
from __future__ import annotations

import tempfile
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from pathlib import Path
from uuid import uuid4


@asynccontextmanager
async def temp_audio_file(data: bytes, suffix: str) -> AsyncIterator[Path]:
    """Write `data` to a throwaway temp file for the duration of the `with`
    block (STT libraries generally need a file path, not raw bytes)."""
    path = Path(tempfile.gettempdir()) / f"aurora_upload_{uuid4().hex}{suffix}"
    path.write_bytes(data)
    try:
        yield path
    finally:
        path.unlink(missing_ok=True)
