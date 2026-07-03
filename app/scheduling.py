"""Pure next_run_at calculation.

No I/O, no database session, no HTTP calls. Given a schedule's trigger
fields and the configured location/timezone, what is the next UTC
instant it should fire?

Deliberately kept separate from scheduler.py (the background polling
loop, not yet built). The routers need this today, on create and on
update; the loop's daily sunrise/sunset recompute will need the exact
same function later. Neither should have to depend on the other.
"""

from datetime import date, datetime, time, timedelta
from zoneinfo import ZoneInfo

from app.models import Settings, TriggerType
from app.sun import LocationNotConfigured, sun_times

# A week plus one. Guarantees a hit even in the edge case where only
# one day of the week is enabled and we just missed it for this week.
_LOOKAHEAD_DAYS = 8

# For annual repeat: worst case is we just missed the last day of the
# window, so the next occurrence is almost a full year away.
_ANNUAL_LOOKAHEAD_DAYS = 366 + _LOOKAHEAD_DAYS


class NoNextRunError(Exception):
    """Raised when a schedule has no future occurrence in its date range."""


def _day_bit(d: date) -> int:
    """Monday=bit 0 ... Sunday=bit 6, matching the bitmask convention
    used on Schedule.days_of_week in app.models."""
    return 1 << d.weekday()


def _in_annual_window(candidate: date, start: date, end: date) -> bool:
    """Check if candidate's (month, day) falls within the [start, end]
    month-day window. Handles cross-year windows (e.g. Dec 15 → Jan 15)
    where end's month+day is numerically before start's."""
    s = (start.month, start.day)
    e = (end.month, end.day)
    c = (candidate.month, candidate.day)
    if s <= e:
        return s <= c <= e
    # Cross-year wrap: in-range means on-or-after start OR on-or-before end
    return c >= s or c <= e


def compute_next_run_at(
    *,
    trigger_type: TriggerType,
    time_of_day: time | None,
    offset_minutes: int | None,
    days_of_week: int,
    settings: Settings,
    now_utc: datetime,
    start_date: date | None = None,
    end_date: date | None = None,
    repeat_annually: bool = False,
) -> datetime | None:
    """Returns the next occurrence as a naive UTC datetime, strictly
    after now_utc, or None if the schedule has no future run in the range.
    Raises LocationNotConfigured if a sunrise/sunset schedule is requested
    before latitude/longitude/timezone are set."""
    is_sun_trigger = trigger_type in (TriggerType.SUNRISE, TriggerType.SUNSET)

    if is_sun_trigger and (
        settings.latitude is None or settings.longitude is None or settings.timezone is None
    ):
        raise LocationNotConfigured(
            "latitude, longitude, and timezone must be set before a "
            "sunrise or sunset schedule can be created"
        )

    tz = ZoneInfo(settings.timezone) if settings.timezone else ZoneInfo("UTC")
    now_local = now_utc.replace(tzinfo=ZoneInfo("UTC")).astimezone(tz)

    # annual=True only when both bounds are provided; otherwise falls
    # back to normal (one-shot or unbounded) date-range behaviour.
    annual = repeat_annually and start_date is not None and end_date is not None

    if annual:
        search_start = now_local.date()
        search_end = search_start + timedelta(days=_ANNUAL_LOOKAHEAD_DAYS)
    else:
        if start_date is not None and end_date is not None and end_date < start_date:
            raise ValueError("end_date must be the same as or after start_date")

        search_start = now_local.date()
        if start_date is not None and start_date > search_start:
            search_start = start_date

        if end_date is not None and search_start > end_date:
            return None

        search_end = (
            end_date
            if end_date is not None
            else search_start + timedelta(days=_LOOKAHEAD_DAYS)
        )

    candidate_date = search_start
    while candidate_date <= search_end:
        in_window = _in_annual_window(candidate_date, start_date, end_date) if annual else True

        if in_window and (days_of_week & _day_bit(candidate_date)):
            if trigger_type == TriggerType.TIME:
                candidate_local = datetime.combine(candidate_date, time_of_day, tzinfo=tz)
            else:
                events = sun_times(
                    settings.latitude,
                    settings.longitude,
                    settings.timezone,
                    candidate_date,
                )
                base = (
                    events["sunrise"]
                    if trigger_type == TriggerType.SUNRISE
                    else events["sunset"]
                )
                candidate_local = base + timedelta(minutes=offset_minutes)

            if candidate_local > now_local:
                return candidate_local.astimezone(ZoneInfo("UTC")).replace(tzinfo=None)

        candidate_date += timedelta(days=1)

        if (
            not annual
            and end_date is None
            and candidate_date
            > search_start + timedelta(days=_LOOKAHEAD_DAYS)
        ):
            break

    return None
