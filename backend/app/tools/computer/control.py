"""Validated mouse/keyboard automation via pyautogui.

This is the single highest-risk capability in the system: it can click or
type anywhere on the user's real desktop. Every action here is validated
before pyautogui ever touches the OS, and pyautogui's own FAILSAFE stays
enabled (moving the mouse to a screen corner aborts whatever's running) as a
manual escape hatch on top of our own checks.
"""
from __future__ import annotations

import re
from typing import Any

MAX_TEXT_LENGTH = 1000

_pyautogui: Any = None


def _pg() -> Any:
    """Import pyautogui lazily, on first actual use.

    Importing pyautogui eagerly (at module level) transitively imports
    mouseinfo, which on Linux immediately opens an X11 Display connection
    -- this crashes the whole process with `KeyError: 'DISPLAY'` on any
    headless host (found via testing: the Docker container, which has no
    X server, crash-looped on startup because this module is imported by
    app.tools.bootstrap regardless of platform or of whether computer
    control is even enabled). Deferring the import means the rest of the
    application works fine everywhere; only an actual mouse/keyboard call
    on an unsupported host fails, with a clear error, at the point of use.
    """
    global _pyautogui
    if _pyautogui is None:
        import pyautogui as _pg_module

        _pg_module.FAILSAFE = True
        _pg_module.PAUSE = 0.05  # small delay between primitive actions, matches human-ish pacing
        _pyautogui = _pg_module
    return _pyautogui

# Combos that are disproportionately disruptive or a privilege-escalation /
# lockout risk if triggered unintentionally by a model.
_DENYLISTED_COMBOS = {
    "alt+f4",       # closes the focused window/app outright
    "win+l",        # locks the session -- may lock the user out pending a password
    "win+r",        # opens Run -- arbitrary-program-launch vector
    "ctrl+alt+delete",
    "ctrl+alt+del",
}

_VALID_KEY_TOKEN = re.compile(r"^[a-z0-9]+$")


class InvalidActionError(Exception):
    pass


class ScreenBoundsError(Exception):
    pass


def get_screen_bounds() -> tuple[int, int, int, int]:
    """(min_x, min_y, max_x, max_y) across all monitors combined."""
    import mss

    with mss.mss() as sct:
        combined = sct.monitors[0]  # index 0 = bounding box of every monitor
        return (
            combined["left"],
            combined["top"],
            combined["left"] + combined["width"],
            combined["top"] + combined["height"],
        )


def validate_coordinates(x: int, y: int) -> None:
    min_x, min_y, max_x, max_y = get_screen_bounds()
    if not (min_x <= x < max_x and min_y <= y < max_y):
        raise ScreenBoundsError(
            f"({x}, {y}) is outside the visible screen area ({min_x}..{max_x}, {min_y}..{max_y})"
        )


def validate_key(key: str) -> list[str]:
    """Parse a '+'-joined key combo (e.g. 'ctrl+c') and validate it. Returns
    the individual key tokens for pyautogui.hotkey()/press()."""
    normalized = key.strip().lower()
    if normalized in _DENYLISTED_COMBOS:
        raise InvalidActionError(f"'{key}' is not allowed (disproportionately disruptive/risky).")

    tokens = [t.strip() for t in normalized.split("+") if t.strip()]
    if not tokens:
        raise InvalidActionError("No key specified")
    for token in tokens:
        if not _VALID_KEY_TOKEN.match(token):
            raise InvalidActionError(f"Unrecognized key token: '{token}'")
    return tokens


def click(x: int, y: int, button: str = "left") -> None:
    validate_coordinates(x, y)
    _pg().click(x=x, y=y, button=button)


def double_click(x: int, y: int) -> None:
    validate_coordinates(x, y)
    _pg().doubleClick(x=x, y=y)


def move_mouse(x: int, y: int) -> None:
    validate_coordinates(x, y)
    _pg().moveTo(x, y)


def type_text(text: str) -> None:
    if len(text) > MAX_TEXT_LENGTH:
        raise InvalidActionError(f"Text is {len(text)} chars, exceeding the {MAX_TEXT_LENGTH}-char limit")
    _pg().typewrite(text, interval=0.01)


def press_key(key: str) -> None:
    tokens = validate_key(key)
    if len(tokens) == 1:
        _pg().press(tokens[0])
    else:
        _pg().hotkey(*tokens)


def scroll(amount: int, x: int | None = None, y: int | None = None) -> None:
    if x is not None and y is not None:
        validate_coordinates(x, y)
    _pg().scroll(amount, x=x, y=y)
