"""Security tests: network security / SSRF guard (spec section 68).

Exercises the real running backend's open_url tool against the actual
network stack -- these targets genuinely resolve to loopback/private
addresses, so this proves the guard, not a mock of it.
"""
from __future__ import annotations

import pytest


@pytest.mark.parametrize(
    "url",
    [
        "http://localhost:8000/",
        "http://127.0.0.1:8000/",
        "http://169.254.169.254/latest/meta-data/",  # cloud metadata endpoint
        "ftp://example.com/",
        "file:///etc/passwd",
    ],
)
def test_open_url_refuses_internal_and_non_http_targets(api_client, url):
    response = api_client.post("/api/tools/open_url/execute", json={"arguments": {"url": url}})
    body = response.json()
    assert body["success"] is False
    assert body["error"]["code"] == "URL_BLOCKED"
