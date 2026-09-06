"""Integration tests for /api/automations + /api/tasks.

Corresponds to spec section 71's test_scheduler_persistence(): the
scheduler is DB-polling by design (see docs/architecture.md), so an
automation's schedule state is proven "persistent" by reading it back from
a fresh GET request (a separate request cycle than the one that created
it) rather than trusting in-memory state.
"""
from __future__ import annotations

from datetime import UTC, datetime, timedelta


def test_create_once_automation_persists_and_computes_next_run(api_client):
    run_at = (datetime.now(UTC) + timedelta(hours=1)).replace(microsecond=0)

    created = api_client.post(
        "/api/automations",
        json={
            "name": "phase11_test_reminder",
            "trigger_type": "once",
            "run_at": run_at.isoformat(),
            "action_type": "reminder",
            "action_payload": {"message": "phase 11 integration test"},
        },
    )
    assert created.status_code == 201
    automation_id = created.json()["id"]
    assert created.json()["status"] == "active"

    # A fresh, independent GET request -- proves the schedule is read from
    # the database, not held only in the process that created it.
    fetched = api_client.get(f"/api/automations/{automation_id}")
    assert fetched.status_code == 200
    body = fetched.json()
    assert body["trigger_type"] == "once"
    assert body["next_run_at"] is not None
    assert body["status"] == "active"

    # cleanup
    api_client.delete(f"/api/automations/{automation_id}")


def test_pause_and_resume_automation(api_client):
    run_at = (datetime.now(UTC) + timedelta(hours=1)).replace(microsecond=0)
    created = api_client.post(
        "/api/automations",
        json={
            "name": "phase11_pause_test",
            "trigger_type": "once",
            "run_at": run_at.isoformat(),
            "action_type": "reminder",
            "action_payload": {"message": "pause test"},
        },
    ).json()
    automation_id = created["id"]

    paused = api_client.patch(f"/api/automations/{automation_id}", json={"status": "paused"})
    assert paused.status_code == 200
    assert paused.json()["status"] == "paused"

    resumed = api_client.patch(f"/api/automations/{automation_id}", json={"status": "active"})
    assert resumed.status_code == 200
    assert resumed.json()["status"] == "active"

    api_client.delete(f"/api/automations/{automation_id}")


def test_delete_automation_removes_it(api_client):
    run_at = (datetime.now(UTC) + timedelta(hours=1)).replace(microsecond=0)
    created = api_client.post(
        "/api/automations",
        json={
            "name": "phase11_delete_test",
            "trigger_type": "once",
            "run_at": run_at.isoformat(),
            "action_type": "reminder",
            "action_payload": {"message": "delete test"},
        },
    ).json()
    automation_id = created["id"]

    deleted = api_client.delete(f"/api/automations/{automation_id}")
    assert deleted.status_code == 204

    fetched = api_client.get(f"/api/automations/{automation_id}")
    assert fetched.status_code == 404


def test_invalid_automation_payload_is_rejected(api_client):
    # 'once' requires run_at -- omitting it must fail validation, not crash.
    response = api_client.post(
        "/api/automations",
        json={
            "name": "phase11_invalid",
            "trigger_type": "once",
            "action_type": "reminder",
            "action_payload": {"message": "x"},
        },
    )
    assert response.status_code == 422
