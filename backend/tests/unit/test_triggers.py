"""Unit tests for app.automation.triggers.compute_next_run.

Corresponds to spec section 71's test_scheduler_persistence() (the pure
scheduling math that persistence relies on) and section 70's "scheduler"
unit-test requirement. Uses plain unpersisted Automation instances -- no
database needed, since compute_next_run only reads attributes.
"""
from __future__ import annotations

from datetime import datetime, timedelta

import pytest

from app.automation.triggers import InvalidTriggerError, compute_next_run
from app.database.models import Automation


def _automation(**kwargs) -> Automation:
    defaults = dict(name="test", action_type="reminder", action_payload={}, status="active")
    defaults.update(kwargs)
    return Automation(**defaults)


def test_once_trigger_returns_run_at_when_never_run():
    run_at = datetime(2026, 9, 6, 12, 0, 0)
    automation = _automation(trigger_type="once", run_at=run_at)
    assert compute_next_run(automation) == run_at


def test_once_trigger_returns_none_after_it_has_run():
    automation = _automation(
        trigger_type="once", run_at=datetime(2026, 9, 6, 12, 0, 0), last_run_at=datetime(2026, 9, 6, 12, 0, 5)
    )
    assert compute_next_run(automation) is None


def test_once_trigger_without_run_at_raises():
    automation = _automation(trigger_type="once", run_at=None)
    with pytest.raises(InvalidTriggerError):
        compute_next_run(automation)


def test_interval_trigger_adds_seconds_to_last_run():
    last_run = datetime(2026, 9, 6, 12, 0, 0)
    automation = _automation(trigger_type="interval", interval_seconds=300, last_run_at=last_run)
    assert compute_next_run(automation) == last_run + timedelta(seconds=300)


def test_interval_trigger_with_no_prior_run_uses_reference_time():
    reference = datetime(2026, 9, 6, 12, 0, 0)
    automation = _automation(trigger_type="interval", interval_seconds=60, last_run_at=None)
    assert compute_next_run(automation, after=reference) == reference + timedelta(seconds=60)


def test_interval_trigger_requires_positive_interval():
    automation = _automation(trigger_type="interval", interval_seconds=0)
    with pytest.raises(InvalidTriggerError):
        compute_next_run(automation)


def test_cron_trigger_computes_next_occurrence():
    reference = datetime(2026, 9, 6, 12, 0, 0)
    automation = _automation(trigger_type="cron", cron_expression="0 9 * * *", last_run_at=None)
    next_run = compute_next_run(automation, after=reference)
    assert next_run == datetime(2026, 9, 7, 9, 0, 0)


def test_cron_trigger_rejects_invalid_expression():
    automation = _automation(trigger_type="cron", cron_expression="not a cron expression")
    with pytest.raises(InvalidTriggerError):
        compute_next_run(automation)


def test_unknown_trigger_type_raises():
    automation = _automation(trigger_type="whenever")
    with pytest.raises(InvalidTriggerError):
        compute_next_run(automation)
