"""Security tests: unauthorized tool calls (spec section 70's security-test list)."""
from __future__ import annotations

import pytest


@pytest.mark.parametrize(
    "tool_name",
    ["not_a_real_tool", "delete_everything", "../delete_file", "os.system"],
)
def test_calling_a_nonexistent_tool_is_refused_safely(api_client, tool_name):
    response = api_client.post(f"/api/tools/{tool_name}/execute", json={"arguments": {}})
    # The route must never 500 or crash -- always a clean structured refusal.
    assert response.status_code in (200, 404)
    if response.status_code == 200:
        body = response.json()
        assert body["success"] is False
        assert body["error"]["code"] == "UNKNOWN_TOOL"


def test_calling_a_tool_with_wrong_argument_types_is_refused_not_crashed(api_client):
    response = api_client.post(
        "/api/tools/create_file/execute",
        json={"arguments": {"path": 12345, "content": {"not": "a string"}}},
    )
    assert response.status_code == 200
    body = response.json()
    assert body["success"] is False
    assert body["error"]["code"] == "INVALID_ARGUMENTS"
