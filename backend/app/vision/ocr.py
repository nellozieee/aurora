"""OCR via Tesseract (through pytesseract).

Reports unavailable rather than crashing if the Tesseract binary isn't
installed -- same pattern as an unconfigured AI provider.
"""
from __future__ import annotations

import io
import shutil
from pathlib import Path

from PIL import Image

# Common Windows install location -- winget/the official installer put it
# here, and it's frequently not yet on PATH in the same session it was
# installed in.
_WINDOWS_FALLBACK_PATH = Path(r"C:\Program Files\Tesseract-OCR\tesseract.exe")


class OCRUnavailableError(Exception):
    pass


def _tesseract_cmd() -> str | None:
    found = shutil.which("tesseract")
    if found:
        return found
    if _WINDOWS_FALLBACK_PATH.exists():
        return str(_WINDOWS_FALLBACK_PATH)
    return None


def is_ocr_available() -> bool:
    return _tesseract_cmd() is not None


def extract_text(png_bytes: bytes) -> str:
    cmd = _tesseract_cmd()
    if cmd is None:
        raise OCRUnavailableError(
            "Tesseract OCR is not installed. Install it (e.g. `winget install "
            "tesseract-ocr.tesseract`) and ensure it's on PATH, or restart the backend."
        )

    import pytesseract

    pytesseract.pytesseract.tesseract_cmd = cmd
    image = Image.open(io.BytesIO(png_bytes))
    return pytesseract.image_to_string(image).strip()
