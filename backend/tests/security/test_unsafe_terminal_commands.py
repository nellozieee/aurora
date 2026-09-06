"""Security tests: unsafe terminal commands (spec section 70's security-test list).

Exercises the real sandboxed code-execution tool via the live API (see
tests/unit/test_sandbox_validate_code.py for the pure denylist logic).
"""
from __future__ import annotations

import pytest


@pytest.mark.parametrize(
    "code",
    [
        "import os\nos.system('whoami')",
        "import subprocess\nsubprocess.run(['whoami'])",
        "import shutil\nshutil.rmtree('C:/Users')",
        "import socket\ns = socket.socket()",
    ],
)
def test_dangerous_code_is_refused_before_execution(api_client, code):
    response = api_client.post(
        "/api/tools/execute_python_code/execute", json={"arguments": {"code": code}}
    )
    body = response.json()
    assert body["success"] is False
    assert body["error"]["code"] == "UNSAFE_CODE"


def test_safe_computational_code_executes_and_returns_real_output(api_client):
    response = api_client.post(
        "/api/tools/execute_python_code/execute",
        json={"arguments": {"code": "print(2 + 2)"}},
    )
    body = response.json()
    assert body["success"] is True
    assert body["data"]["stdout"].strip() == "4"
    assert body["data"]["exit_code"] == 0


def test_infinite_loop_is_killed_by_the_sandbox_timeout(api_client):
    response = api_client.post(
        "/api/tools/execute_python_code/execute",
        json={"arguments": {"code": "while True:\n    pass"}},
    )
    body = response.json()
    assert body["success"] is False
    assert body["error"]["code"] == "TIMEOUT"
