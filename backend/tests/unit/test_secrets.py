"""Unit tests for app.security.secrets.redact().

Corresponds to spec section 71's test_secret_redaction(). Includes a
regression test for a real bug found via live testing during Phase 10: a
naive blind-substring redactor mangled unrelated text because this
project's own dev DB password ("aurora") is the same string as the project
directory name -- see memory/aurora_secret_redaction_false_positive.md.
"""
from __future__ import annotations

import pytest

from app.core.config import get_settings
from app.security import secrets as secrets_module


@pytest.fixture()
def with_fake_secrets(monkeypatch):
    monkeypatch.setenv("OPENAI_API_KEY", "sk-fake-test-key-abc123")
    monkeypatch.setenv("DATABASE_URL", "postgresql+asyncpg://aurora:aurora@localhost:5432/aurora")
    get_settings.cache_clear()
    secrets_module._opaque_secrets_cached.cache_clear()
    yield
    get_settings.cache_clear()
    secrets_module._opaque_secrets_cached.cache_clear()


def test_opaque_api_key_is_redacted(with_fake_secrets):
    msg = "API key sk-fake-test-key-abc123 was rejected"
    assert "sk-fake-test-key-abc123" not in secrets_module.redact(msg)
    assert "***REDACTED***" in secrets_module.redact(msg)


def test_connection_string_password_is_redacted_in_url_context(with_fake_secrets):
    msg = "Connection failed: postgresql+asyncpg://aurora:aurora@localhost:5432/aurora"
    redacted = secrets_module.redact(msg)
    assert "://aurora:***REDACTED***@" in redacted
    # host/db name portions must be untouched
    assert "localhost:5432/aurora" in redacted


def test_password_value_outside_url_context_is_not_touched(with_fake_secrets):
    """Regression test: the dev DB password ("aurora") must not be redacted
    when it appears as ordinary text (e.g. a file path), only when it
    appears as actual URL credentials."""
    path = r"D:\SteamLibrary\aurora\sandbox\workspace\phase10_test.txt"
    assert secrets_module.redact(path) == path


def test_redact_value_recurses_through_dict_and_list(with_fake_secrets):
    payload = {
        "error": "key sk-fake-test-key-abc123 invalid",
        "nested": {"items": ["ok", "sk-fake-test-key-abc123"]},
    }
    redacted = secrets_module.redact_value(payload)
    assert "sk-fake-test-key-abc123" not in str(redacted)


def test_redact_handles_empty_and_none_safely():
    assert secrets_module.redact("") == ""
    assert secrets_module.redact_value(None) is None
    assert secrets_module.redact_value(42) == 42
