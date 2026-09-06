"""Filesystem path security.

Every file tool must resolve paths through here. Resolution is fail-closed:
if no allowed roots are configured, or the resolved path doesn't sit inside
one of them, access is refused -- never silently widened.
"""
from __future__ import annotations

from pathlib import Path

from app.core.config import Settings


class PathSecurityError(Exception):
    """Raised when a requested path falls outside every allowed root."""


def resolve_safe_path(requested_path: str, settings: Settings) -> Path:
    """Resolve `requested_path` and verify it stays inside an allowed root.

    Resolution follows symlinks and normalizes `..`/`.` segments *before* the
    containment check, so neither can be used to escape the allowed roots.
    """
    allowed_roots = settings.allowed_filesystem_paths
    if not allowed_roots:
        raise PathSecurityError(
            "No allowed filesystem paths are configured "
            "(set SECURITY_ALLOWED_FILESYSTEM_PATHS to enable file tools)"
        )

    resolved_roots = [Path(root).expanduser().resolve() for root in allowed_roots]

    candidate = Path(requested_path)
    if not candidate.is_absolute():
        # Relative paths are resolved against the first allowed root, not the
        # process's CWD -- otherwise the "allowed roots" check would be
        # trivially bypassable by the CWD the server happens to run from.
        candidate = resolved_roots[0] / candidate

    try:
        resolved = candidate.resolve()
    except OSError as exc:
        raise PathSecurityError(f"Could not resolve path: {requested_path}") from exc

    for root in resolved_roots:
        try:
            resolved.relative_to(root)
            return resolved
        except ValueError:
            continue

    raise PathSecurityError(
        f"Path '{requested_path}' is outside all allowed directories: "
        f"{', '.join(str(r) for r in resolved_roots)}"
    )
