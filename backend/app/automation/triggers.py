"""Computes when an Automation should next fire."""
from __future__ import annotations

from datetime import datetime, timedelta

from app.database.models import Automation
from app.utils.time import utc_now


class InvalidTriggerError(Exception):
    pass


def compute_next_run(automation: Automation, *, after: datetime | None = None) -> datetime | None:
    """Returns the next run time, or None if the automation has no more runs
    (a 'once' trigger that already fired)."""
    reference = after or utc_now()

    if automation.trigger_type == "once":
        if automation.last_run_at is not None:
            return None
        if automation.run_at is None:
            raise InvalidTriggerError("'once' automations require run_at")
        return automation.run_at

    if automation.trigger_type == "interval":
        if not automation.interval_seconds or automation.interval_seconds <= 0:
            raise InvalidTriggerError("'interval' automations require a positive interval_seconds")
        base = automation.last_run_at or reference
        return base + timedelta(seconds=automation.interval_seconds)

    if automation.trigger_type == "cron":
        if not automation.cron_expression:
            raise InvalidTriggerError("'cron' automations require cron_expression")
        from croniter import croniter

        if not croniter.is_valid(automation.cron_expression):
            raise InvalidTriggerError(f"Invalid cron expression: {automation.cron_expression!r}")
        base = automation.last_run_at or reference
        return croniter(automation.cron_expression, base).get_next(datetime)

    raise InvalidTriggerError(f"Unknown trigger_type: {automation.trigger_type!r}")
