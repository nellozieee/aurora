"""Unit tests for app.core.config.Settings.

Corresponds to spec section 70's "configuration" unit-test requirement.
"""
from __future__ import annotations

from app.core.config import Settings


def test_defaults_allow_startup_without_any_env_vars():
    settings = Settings(_env_file=None)
    assert settings.app_name == "Aurora"
    assert settings.security_computer_control_enabled is False
    assert settings.openai_api_key == ""
    assert settings.telegram_bot_token == ""


def test_cors_allowed_origins_splits_and_strips():
    settings = Settings(_env_file=None, APP_CORS_ORIGINS="http://a.test, http://b.test ,http://c.test")
    assert settings.cors_allowed_origins == ["http://a.test", "http://b.test", "http://c.test"]


def test_cors_allowed_origins_empty_string_yields_empty_list():
    settings = Settings(_env_file=None, APP_CORS_ORIGINS="")
    assert settings.cors_allowed_origins == []


def test_allowed_filesystem_paths_empty_by_default():
    settings = Settings(_env_file=None, SECURITY_ALLOWED_FILESYSTEM_PATHS="")
    assert settings.allowed_filesystem_paths == []


def test_relative_allowed_filesystem_path_resolves_against_repo_root():
    settings = Settings(_env_file=None, SECURITY_ALLOWED_FILESYSTEM_PATHS="./sandbox/workspace")
    resolved = settings.allowed_filesystem_paths
    assert len(resolved) == 1
    assert resolved[0].endswith("sandbox/workspace") or resolved[0].endswith("sandbox\\workspace")
    import os

    assert os.path.isabs(resolved[0])


def test_absolute_allowed_filesystem_path_is_kept_as_is(tmp_path):
    settings = Settings(_env_file=None, SECURITY_ALLOWED_FILESYSTEM_PATHS=str(tmp_path))
    assert settings.allowed_filesystem_paths == [str(tmp_path)]
