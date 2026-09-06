"""Shared test fixtures.

Consistent with how every prior phase of this project was verified (real
Postgres, real Redis, real Ollama -- never mocks of the core behavior),
integration/security/E2E tests here exercise the actual running backend at
`BASE_URL` and the actual dev database, rather than a separate mocked stack.
Tests that need the live server skip cleanly (not fail) when it isn't
running, via `require_server`. Unit tests never touch the network or a
running server.
"""
from __future__ import annotations

import httpx
import pytest

BASE_URL = "http://localhost:8000"


def _server_reachable() -> bool:
    try:
        httpx.get(f"{BASE_URL}/api/system/health", timeout=2.0)
        return True
    except httpx.HTTPError:
        return False


@pytest.fixture(scope="session")
def require_server():
    if not _server_reachable():
        pytest.skip(
            f"Backend is not running at {BASE_URL} -- start it with "
            "'uvicorn app.main:app' before running integration/security/E2E tests."
        )


@pytest.fixture()
def api_client(require_server):
    # A generous timeout: the sandbox-timeout security test deliberately
    # runs an infinite loop and waits for the *server's own*
    # SECURITY_SANDBOX_TIMEOUT_SECONDS (default 30s) to kill it.
    with httpx.Client(base_url=BASE_URL, timeout=45.0) as client:
        yield client


def _ollama_reachable() -> bool:
    try:
        httpx.get("http://localhost:11434/api/version", timeout=2.0)
        return True
    except httpx.HTTPError:
        return False


@pytest.fixture(scope="session")
def require_ollama():
    if not _ollama_reachable():
        pytest.skip("Ollama is not running at localhost:11434 -- required for E2E chat tests.")
