from __future__ import annotations

import threading
from datetime import datetime, time, timedelta


def next_run_at(
    now: datetime,
    last_run: datetime | None,
    interval_days: int,
    hour: int,
    minute: int,
) -> datetime:
    """Return the next scheduled run at HH:MM, every interval_days."""
    if interval_days < 1:
        raise ValueError("interval_days must be >= 1")

    if last_run is None:
        candidate = datetime.combine(now.date(), time(hour, minute), tzinfo=now.tzinfo)
        if candidate <= now:
            candidate += timedelta(days=1)
        return candidate

    candidate = datetime.combine(
        last_run.date() + timedelta(days=interval_days),
        time(hour, minute),
        tzinfo=now.tzinfo,
    )
    while candidate <= now:
        candidate += timedelta(days=interval_days)
    return candidate


def sleep_until(target: datetime, stop_event: threading.Event, chunk_seconds: float = 30.0) -> bool:
    """Sleep until target; return False when the stop event is set."""
    while True:
        remaining = (target - datetime.now(target.tzinfo)).total_seconds()
        if remaining <= 0:
            return not stop_event.is_set()
        if stop_event.wait(min(remaining, chunk_seconds)):
            return False
