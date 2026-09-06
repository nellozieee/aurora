"""Integration tests for /api/tools (list + manual execution).

Corresponds to spec section 70's "tool execution" integration requirement.
"""
from __future__ import annotations


def test_list_tools_returns_every_registered_tool(api_client):
    response = api_client.get("/api/tools")
    assert response.status_code == 200
    tools = response.json()
    names = {t["name"] for t in tools}

    # A representative tool from each risk tier must be present.
    assert "web_search" in names
    assert "create_reminder" in names
    assert "delete_file" in names
    assert "click" in names
    for tool in tools:
        assert tool["risk_level"] in {"safe", "low", "medium", "high", "critical"}
        assert tool["permission_level"] in {"safe", "user", "confirm"}


def test_confirm_level_tools_are_exactly_the_expected_set(api_client):
    tools = api_client.get("/api/tools").json()
    confirm_tools = {t["name"] for t in tools if t["permission_level"] == "confirm"}
    assert confirm_tools == {"delete_file", "click", "double_click", "type_text", "press_key"}


def test_execute_safe_tool_via_manual_api(api_client):
    response = api_client.post("/api/tools/get_system_info/execute", json={"arguments": {}})
    assert response.status_code == 200
    body = response.json()
    assert body["success"] is True
    assert body["data"]["platform"]
    assert body["data"]["cpu_count"] >= 1


def test_execute_unknown_tool_returns_structured_error(api_client):
    response = api_client.post("/api/tools/not_a_real_tool/execute", json={"arguments": {}})
    assert response.status_code == 200  # never a raw 500 -- always a structured ToolResult
    body = response.json()
    assert body["success"] is False
    assert body["error"]["code"] == "UNKNOWN_TOOL"


def test_file_tools_create_read_delete_roundtrip(api_client):
    filename = "phase11_integration_test.txt"
    content = "created by the Phase 11 integration test suite"

    created = api_client.post(
        "/api/tools/create_file/execute",
        json={"arguments": {"path": filename, "content": content, "overwrite": True}},
    ).json()
    assert created["success"] is True

    read_back = api_client.post(
        "/api/tools/read_file/execute", json={"arguments": {"path": filename}}
    ).json()
    assert read_back["success"] is True
    assert read_back["data"]["content"] == content

    deleted = api_client.post(
        "/api/tools/delete_file/execute",
        json={"arguments": {"path": filename, "confirm": True}},
    ).json()
    assert deleted["success"] is True
    assert deleted["data"]["deleted"] is True
