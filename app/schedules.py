"""Trading-hours helpers based on Trading 212 exchange schedules."""
from __future__ import annotations

from datetime import datetime

from .trading212 import Instrument, WorkingSchedule

_REGULAR_OPEN = {"OPEN", "BREAK_END"}
_REGULAR_CLOSE = {"CLOSE", "BREAK_START"}
_EXTENDED_OPEN = {"PRE_MARKET_OPEN", "AFTER_HOURS_OPEN", "OVERNIGHT_OPEN"}
_EXTENDED_CLOSE = {"AFTER_HOURS_CLOSE"}


def is_schedule_open(schedule: WorkingSchedule, now: datetime, allow_extended_hours: bool) -> bool:
    latest_event = None
    for event in sorted(schedule.events, key=lambda item: item.when):
        if event.when <= now:
            latest_event = event
        else:
            break
    if latest_event is None:
        return False
    if latest_event.event_type in _REGULAR_OPEN:
        return True
    if latest_event.event_type in _REGULAR_CLOSE | _EXTENDED_CLOSE:
        return False
    if latest_event.event_type in _EXTENDED_OPEN:
        return allow_extended_hours
    return False


def instrument_is_tradable(
    ticker: str,
    instruments: dict[str, Instrument],
    schedules: dict[int, WorkingSchedule],
    now: datetime,
    allow_extended_hours: bool,
) -> bool:
    instrument = instruments.get(ticker)
    if instrument is None or instrument.working_schedule_id is None:
        return False
    schedule = schedules.get(instrument.working_schedule_id)
    if schedule is None:
        return False
    return is_schedule_open(schedule, now, allow_extended_hours)
