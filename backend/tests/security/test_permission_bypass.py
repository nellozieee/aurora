"""Security tests: permission bypass (spec section 70's security-test list).

Corresponds to spec section 71's test_delete_requires_confirmation(), run
against the real running backend (see tests/unit/test_permissions.py for
the pure-function version of the same guarantee).
"""
from __future__ import annotations

import pytest


@pytest.mark.parametrize(
    "tool,arguments",
    [
        ("delete_file", {"path": "should_never_be_created.txt"}),
        ("click", {"x": 10, "y": 10}),
        ("double_click", {"x": 10, "y": 10}),
        ("type_text", {"text": "hello"}),
        ("press_key", {"key": "enter"}),
    ],
)
def test_confirm_level_tools_are_denied_without_confirm_flag(api_client, tool, arguments):
    response = api_client.post(f"/api/tools/{tool}/execute", json={"arguments": arguments})
    body = response.json()
    assert body["success"] is False
    assert body["error"]["code"] == "PERMISSION_REQUIRED"
    assert body["metadata"]["permission_status"] == "denied"


def test_confirm_flag_as_non_boolean_truthy_string_is_still_denied(api_client):
    """A model or a hand-crafted API call passing "confirm": "true" (a string,
    not the JSON boolean) must not be treated as granted -- only literal true."""
    response = api_client.post(
        "/api/tools/delete_file/execute",
        json={"arguments": {"path": "x.txt", "confirm": "true"}},
    )
    body = response.json()
    assert body["success"] is False
    assert body["error"]["code"] == "PERMISSION_REQUIRED"


def test_computer_control_stays_disabled_even_with_confirm_true(api_client):
    """Two independent gates must both allow: the centralized permission
    engine (confirm=true) and the separate hard SECURITY_COMPUTER_CONTROL_ENABLED
    opt-in, which is off by default in this dev environment."""
    response = api_client.post(
        "/api/tools/click/execute", json={"arguments": {"x": 10, "y": 10, "confirm": True}}
    )
    body = response.json()
    assert body["success"] is False
    assert body["error"]["code"] == "COMPUTER_CONTROL_DISABLED"
    assert body["metadata"]["permission_status"] == "granted"


def test_delete_file_succeeds_with_confirm_true(api_client):
    filename = "phase11_permission_test.txt"
    api_client.post(
        "/api/tools/create_file/execute",
        json={"arguments": {"path": filename, "content": "x", "overwrite": True}},
    )
    response = api_client.post(
        "/api/tools/delete_file/execute", json={"arguments": {"path": filename, "confirm": True}}
    )
    body = response.json()
    assert body["success"] is True
    assert body["metadata"]["permission_status"] == "granted"
