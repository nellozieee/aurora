"""Secret redaction (spec section 64).

Centralized so every log line, tool error, and audit record is protected the
same way instead of each call site remembering to redact by hand. Values are
never reversible from the redacted output -- this does substring replacement
against the actual configured secret values, not pattern-matching.
"""
from __future__ import annotations

import re
from functools import lru_cache

from app.core.config import Settings, get_settings

_MASK = "***REDACTED***"

# Matches the credential portion of a connection URL, e.g. the "user:pass" in
# "postgresql+asyncpg://user:pass@host:5432/db" -- used to redact DB/Redis
# passwords *only* when they appear in that specific URL shape.
#
# Deliberately NOT done via a blind substring match against the raw password
# value: this project's own default dev credentials are postgresql://aurora:
# aurora@..., i.e. the password is literally "aurora" -- the same string as
# the project directory name. A naive `text.replace(password, MASK)` was
# found live to mangle unrelated paths like "D:\SteamLibrary\aurora\..." into
# "D:\SteamLibrary\***REDACTED***\...". Confining the match to an actual
# "://user:PASSWORD@" shape avoids that false positive while still catching
# the real leak vector (a raw connection string surfacing in an error).
_CREDENTIAL_URL_RE = re.compile(r"(://[^/\s:@]+:)([^@\s]+)(@)")


@lru_cache
def _opaque_secrets_cached(settings_id: int) -> tuple[str, ...]:
    # keyed by id(settings) so a Settings() rebuild (e.g. in tests) invalidates the cache
    settings = get_settings()
    return tuple(_collect_opaque_secrets(settings))


def _collect_opaque_secrets(settings: Settings) -> list[str]:
    # High-entropy, long, effectively-unique values -- safe to redact via a
    # blind substring match since an accidental collision with unrelated text
    # is vanishingly unlikely (unlike a short/common DB password).
    values = [
        settings.openai_api_key,
        settings.openrouter_api_key,
        settings.telegram_bot_token,
        settings.app_secret_key,
    ]
    return [v for v in values if v]


def known_secrets() -> tuple[str, ...]:
    return _opaque_secrets_cached(id(get_settings()))


def redact(text: str) -> str:
    """Redact known secrets from `text`: opaque tokens via substring match,
    and any DB/Redis-style connection-string password via its URL shape."""
    if not text:
        return text
    for secret in known_secrets():
        if secret and secret in text:
            text = text.replace(secret, _MASK)
    text = _CREDENTIAL_URL_RE.sub(lambda m: f"{m.group(1)}{_MASK}{m.group(3)}", text)
    return text


def redact_value(value: object) -> object:
    """Recursively redact secrets from strings inside dicts/lists/tuples."""
    if isinstance(value, str):
        return redact(value)
    if isinstance(value, dict):
        return {k: redact_value(v) for k, v in value.items()}
    if isinstance(value, (list, tuple)):
        return type(value)(redact_value(v) for v in value)
    return value
