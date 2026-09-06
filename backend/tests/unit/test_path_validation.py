"""Unit tests for app.security.validators.resolve_safe_path.

Corresponds to spec section 71's test_safe_file_read() / test_blocked_file_access()
and section 67 (path traversal / absolute-path escapes / no-allowed-roots fail-closed).
"""
from __future__ import annotations

import pytest

from app.core.config import Settings
from app.security.validators import PathSecurityError, resolve_safe_path


def _settings_with_root(tmp_path) -> Settings:
    return Settings(SECURITY_ALLOWED_FILESYSTEM_PATHS=str(tmp_path))


def test_relative_path_inside_allowed_root_resolves(tmp_path):
    settings = _settings_with_root(tmp_path)
    resolved = resolve_safe_path("notes.txt", settings)
    assert resolved == (tmp_path / "notes.txt").resolve()


def test_dotdot_traversal_outside_allowed_root_is_blocked(tmp_path):
    settings = _settings_with_root(tmp_path)
    with pytest.raises(PathSecurityError):
        resolve_safe_path("../../../../etc/passwd", settings)


def test_absolute_path_outside_allowed_root_is_blocked(tmp_path):
    """An absolute path pointing anywhere outside the allowed root must be
    blocked, on any OS. Built as a real absolute path on whatever platform
    the test runs on (tmp_path.parent / ...) rather than hardcoding
    Windows drive-letter syntax -- on Linux, "C:\\Windows\\..." isn't
    absolute at all (backslashes aren't path separators), so it would
    resolve as a harmless *relative* filename under the allowed root and
    never raise -- a portability bug, not a security one, caught by
    actually running this suite against a Linux backend (see
    docs/architecture.md's Phase 12 section)."""
    settings = _settings_with_root(tmp_path)
    outside_path = tmp_path.parent / "definitely_outside" / "secret.txt"
    with pytest.raises(PathSecurityError):
        resolve_safe_path(str(outside_path), settings)


def test_absolute_path_inside_allowed_root_is_allowed(tmp_path):
    settings = _settings_with_root(tmp_path)
    target = tmp_path / "subdir" / "file.txt"
    resolved = resolve_safe_path(str(target), settings)
    assert resolved == target.resolve()


def test_no_allowed_roots_configured_is_fail_closed():
    settings = Settings(SECURITY_ALLOWED_FILESYSTEM_PATHS="")
    with pytest.raises(PathSecurityError):
        resolve_safe_path("anything.txt", settings)


def test_symlink_escape_is_blocked(tmp_path):
    """A symlink inside the allowed root pointing outside it must not grant access
    -- resolution follows symlinks before the containment check (section 67)."""
    outside = tmp_path.parent / "outside_target"
    outside.mkdir(exist_ok=True)
    allowed_root = tmp_path / "allowed"
    allowed_root.mkdir()
    settings = Settings(SECURITY_ALLOWED_FILESYSTEM_PATHS=str(allowed_root))

    link = allowed_root / "escape_link"
    try:
        link.symlink_to(outside, target_is_directory=True)
    except OSError:
        pytest.skip("Creating symlinks requires elevated privileges on this system")

    with pytest.raises(PathSecurityError):
        resolve_safe_path(str(link / "secret.txt"), settings)
