"""Integration tests for /api/system health/status.

Corresponds to spec section 70's "database", "Redis", "API" integration
requirements. Exercises the real running backend and its real DB/Redis
connections -- not mocks.
"""
from __future__ import annotations


def test_health_endpoint_is_always_ok(api_client):
    response = api_client.get("/api/system/health")
    assert response.status_code == 200
    assert response.json() == {"status": "ok"}


def test_status_reports_real_subsystem_health(api_client):
    response = api_client.get("/api/system/status")
    assert response.status_code == 200
    body = response.json()

    assert body["assistant_name"] == "Aurora"
    subsystems = body["subsystems"]
    assert subsystems["backend"] == "online"
    # A live run must reflect the real DB/Redis connection state, not a stub.
    assert subsystems["database"] == "online"
    assert subsystems["redis"] == "online"


def test_telegram_reports_not_configured_without_credentials(api_client):
    """Corresponds to spec section 71's test_telegram_disabled_without_credentials()."""
    response = api_client.get("/api/system/status")
    body = response.json()
    # This dev environment has no TELEGRAM_BOT_TOKEN/TELEGRAM_CHAT_ID set.
    assert body["subsystems"]["notifications.telegram"] == "not_configured"
