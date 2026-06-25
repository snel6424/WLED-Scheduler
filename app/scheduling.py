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


def _day_bit(d: date) -> int:
    """Monday=bit 0 ... Sunday=bit 6, matching the bitmask convention
    used on Schedule.days_of_week in app.models."""
    return 1 << d.weekday()


def compute_next_run_at(
    *,
    trigger_type: TriggerType,
    time_of_day: time | None,
    offset_minutes: int | None,
    days_of_week: int,
    settings: Settings,
    now_utc: datetime,
) -> datetime:
    """Returns the next occurrence as a naive UTC datetime, strictly
    after now_utc. Raises LocationNotConfigured if a sunrise/sunset
    schedule is requested before latitude/longitude/timezone are set."""
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

    for day_offset in range(_LOOKAHEAD_DAYS):
        candidate_date = (now_local + timedelta(days=day_offset)).date()
        if not (days_of_week & _day_bit(candidate_date)):
            continue

        if trigger_type == TriggerType.TIME:
            candidate_local = datetime.combine(candidate_date, time_of_day, tzinfo=tz)
        else:
            events = sun_times(
                settings.latitude, settings.longitude, settings.timezone, candidate_date
            )
            base = events["sunrise"] if trigger_type == TriggerType.SUNRISE else events["sunset"]
            candidate_local = base + timedelta(minutes=offset_minutes)

        if candidate_local > now_local:
            return candidate_local.astimezone(ZoneInfo("UTC")).replace(tzinfo=None)

    # Should be unreachable given days_of_week is constrained to 0-127
    # and the lookahead window is longer than a week, but fail loudly
    # rather than silently returning a bad value if it ever is.
    raise RuntimeError("could not find a next occurrence within the lookahead window")
