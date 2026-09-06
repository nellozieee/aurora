"""Security tests: path traversal (spec section 70's security-test list).

Exercises the real running backend's file tools through the actual API,
not just the unit-level resolve_safe_path (see tests/unit/test_path_validation.py).
"""
from __future__ import annotations

import pytest


@pytest.mark.parametrize(
    "path",
    [
        "../../../../windows/win.ini",
        "/etc/passwd",
    ],
)
def test_read_file_blocks_traversal_and_absolute_escapes(api_client, path):
    """Traversal/absolute-path syntax that's meaningful on any OS the
    backend might run on -- must always be refused with PATH_DENIED."""
    response = api_client.post("/api/tools/read_file/execute", json={"arguments": {"path": path}})
    body = response.json()
    assert body["success"] is False
    assert body["error"]["code"] == "PATH_DENIED"


@pytest.mark.parametrize(
    "path",
    [
        "..\\..\\..\\..\\Windows\\System32\\config\\SAM",
        "C:\\Windows\\System32\\drivers\\etc\\hosts",
    ],
)
def test_read_file_blocks_windows_style_escapes(api_client, path):
    """Windows drive-letter/backslash syntax only means something as a
    real escape attempt when the backend itself runs on Windows -- on
    Linux, backslashes aren't path separators, so this resolves to a
    literal (nonexistent) relative filename instead. Both PATH_DENIED and
    NOT_FOUND are secure outcomes here: what actually matters is that no
    file content outside the allowed root is ever returned."""
    response = api_client.post("/api/tools/read_file/execute", json={"arguments": {"path": path}})
    body = response.json()
    assert body["success"] is False
    assert body["error"]["code"] in ("PATH_DENIED", "NOT_FOUND")
    assert "data" not in body or body["data"] is None


def test_search_files_blocks_traversal_outside_allowed_root(api_client):
    response = api_client.post(
        "/api/tools/search_files/execute", json={"arguments": {"root": "../../../"}}
    )
    body = response.json()
    assert body["success"] is False
    assert body["error"]["code"] == "PATH_DENIED"


def test_create_file_blocks_writing_outside_allowed_root(api_client):
    response = api_client.post(
        "/api/tools/create_file/execute",
        json={"arguments": {"path": "../outside_sandbox_escape.txt", "content": "x"}},
    )
    body = response.json()
    assert body["success"] is False
    assert body["error"]["code"] == "PATH_DENIED"
