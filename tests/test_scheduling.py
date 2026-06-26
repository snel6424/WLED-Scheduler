"""Tests for app.scheduling.compute_next_run_at: pure functions, no
database or HTTP involved, just verified against real coordinates.
"""

import datetime as dt

import pytest

from app.models import Settings, TriggerType
from app.scheduling import compute_next_run_at
from app.sun import LocationNotConfigured

OKLAHOMA = Settings(latitude=35.4676, longitude=-97.5164, timezone="America/Chicago")


def test_time_trigger_returns_correct_utc_instant():
    # 1pm Central on a Wednesday in June (CDT, UTC-5)
    now = dt.datetime(2026, 6, 24, 18, 0, 0)
    next_run = compute_next_run_at(
        trigger_type=TriggerType.TIME, time_of_day=dt.time(7, 0), offset_minutes=None,
        days_of_week=127, settings=OKLAHOMA, now_utc=now,
    )
    # 7am tomorrow Central, since 7am already passed today; 7am CDT = 12:00 UTC
    assert next_run == dt.datetime(2026, 6, 25, 12, 0, 0)


def test_sunset_trigger_with_offset_lands_before_real_sunset():
    now = dt.datetime(2026, 6, 24, 18, 0, 0)  # 1pm Central, before sunset
    next_run = compute_next_run_at(
        trigger_type=TriggerType.SUNSET, time_of_day=None, offset_minutes=-10,
        days_of_week=127, settings=OKLAHOMA, now_utc=now,
    )
    assert next_run.date() == dt.date(2026, 6, 25)  # still UTC, so the date rolls over
    assert next_run > now


def test_sunrise_without_location_configured_raises():
    unconfigured = Settings()
    with pytest.raises(LocationNotConfigured):
        compute_next_run_at(
            trigger_type=TriggerType.SUNRISE, time_of_day=None, offset_minutes=5,
            days_of_week=127, settings=unconfigured, now_utc=dt.datetime(2026, 6, 24, 18, 0, 0),
        )


def test_time_trigger_does_not_need_location():
    """Only sunrise/sunset schedules require latitude/longitude/timezone."""
    unconfigured = Settings()
    next_run = compute_next_run_at(
        trigger_type=TriggerType.TIME, time_of_day=dt.time(7, 0), offset_minutes=None,
        days_of_week=127, settings=unconfigured, now_utc=dt.datetime(2026, 6, 24, 18, 0, 0),
    )
    assert next_run is not None


def test_days_of_week_restriction_skips_to_the_correct_future_day():
    # June 24 2026 is a Wednesday. Restricting to Wednesday only, after
    # 7am has already passed today, should land exactly 7 days later.
    now = dt.datetime(2026, 6, 24, 18, 0, 0)
    wednesday_bit = 1 << 2
    next_run = compute_next_run_at(
        trigger_type=TriggerType.TIME, time_of_day=dt.time(7, 0), offset_minutes=None,
        days_of_week=wednesday_bit, settings=OKLAHOMA, now_utc=now,
    )
    assert next_run == dt.datetime(2026, 7, 1, 12, 0, 0)


def test_time_trigger_honors_start_date():
    now = dt.datetime(2026, 6, 24, 18, 0, 0)
    next_run = compute_next_run_at(
        trigger_type=TriggerType.TIME, time_of_day=dt.time(7, 0), offset_minutes=None,
        days_of_week=127, settings=OKLAHOMA, now_utc=now,
        start_date=dt.date(2026, 6, 25), end_date=None,
    )
    assert next_run == dt.datetime(2026, 6, 25, 12, 0, 0)


def test_time_trigger_honors_end_date_and_returns_none_when_expired():
    now = dt.datetime(2026, 6, 24, 18, 0, 0)
    next_run = compute_next_run_at(
        trigger_type=TriggerType.TIME, time_of_day=dt.time(7, 0), offset_minutes=None,
        days_of_week=127, settings=OKLAHOMA, now_utc=now,
        start_date=None, end_date=dt.date(2026, 6, 23),
    )
    assert next_run is None


def test_time_trigger_rejects_invalid_date_range():
    now = dt.datetime(2026, 6, 24, 18, 0, 0)
    with pytest.raises(ValueError):
        compute_next_run_at(
            trigger_type=TriggerType.TIME, time_of_day=dt.time(7, 0), offset_minutes=None,
            days_of_week=127, settings=OKLAHOMA, now_utc=now,
            start_date=dt.date(2026, 6, 26), end_date=dt.date(2026, 6, 25),
        )
