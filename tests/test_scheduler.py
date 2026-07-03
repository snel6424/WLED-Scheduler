"""Tests for app.scheduler: tick() against the five cases that matter
(normal due, stale with catch-up off, stale with catch-up on, not yet
due, disabled), plus one slower test proving the real asyncio loop
fires a schedule entirely on its own through the actual FastAPI
lifespan, not just via a direct tick() call.
"""

import asyncio
import datetime as dt

import pytest

from app import scheduler
from app.database import SessionLocal, ensure_default_settings
from app.models import (
    Action,
    ActionType,
    Device,
    ExecutionStatus,
    Schedule,
    ScheduleExecution,
    TriggerType,
    utcnow,
)


@pytest.fixture
def device_row(db, mock_wled_host):
    device = Device(name="Porch", host=mock_wled_host)
    db.add(device)
    db.flush()
    return device


@pytest.fixture
def action_row(db):
    action = Action(name="Glow", type=ActionType.STATE, payload={"on": True})
    db.add(action)
    db.flush()
    return action


def _make_schedule(db, device, action, **overrides):
    base = dict(
        name="Schedule", devices=[device], action_id=action.id,
        trigger_type=TriggerType.TIME, time_of_day=dt.time(7, 0),
    )
    base.update(overrides)
    schedule = Schedule(**base)
    db.add(schedule)
    db.flush()
    return schedule


def test_normal_due_schedule_fires(db, settings_row, device_row, action_row):
    now = utcnow()
    schedule = _make_schedule(
        db, device_row, action_row, next_run_at=now - dt.timedelta(seconds=5)
    )
    db.commit()

    scheduler.tick()

    db.refresh(schedule)
    executions = db.query(ScheduleExecution).filter_by(schedule_id=schedule.id).all()
    assert len(executions) == 1
    assert executions[0].overall_status == ExecutionStatus.SUCCESS.value
    assert schedule.last_run_at is not None
    assert schedule.next_run_at > utcnow()


def test_schedule_targeting_two_devices_fires_on_both(db, settings_row, device_row, action_row):
    from tests.mock_wled import server as mock_wled

    _, port = mock_wled.start()
    other_device = Device(name="Lamp", host=f"127.0.0.1:{port}")
    db.add(other_device)
    db.flush()

    now = utcnow()
    schedule = Schedule(
        name="Schedule", devices=[device_row, other_device], action_id=action_row.id,
        trigger_type=TriggerType.TIME, time_of_day=dt.time(7, 0),
        next_run_at=now - dt.timedelta(seconds=5),
    )
    db.add(schedule)
    db.commit()

    scheduler.tick()

    db.refresh(schedule)
    executions = db.query(ScheduleExecution).filter_by(schedule_id=schedule.id).all()
    assert len(executions) == 1
    assert executions[0].overall_status == ExecutionStatus.SUCCESS.value
    fired_device_ids = {r["device_id"] for r in executions[0].device_results}
    assert fired_device_ids == {device_row.id, other_device.id}


def test_stale_schedule_with_catch_up_off_is_skipped_not_fired(
    db, settings_row, device_row, action_row
):
    settings_row.catch_up_missed = False
    now = utcnow()
    schedule = _make_schedule(
        db, device_row, action_row, next_run_at=now - dt.timedelta(hours=2)
    )
    db.commit()

    scheduler.tick()

    db.refresh(schedule)
    executions = db.query(ScheduleExecution).filter_by(schedule_id=schedule.id).all()
    assert len(executions) == 1
    assert executions[0].overall_status == ExecutionStatus.SKIPPED.value
    # carries the human-readable reason, one entry per targeted device
    assert executions[0].device_results[0]["error_message"] is not None
    assert schedule.last_run_at is None  # never actually ran
    assert schedule.next_run_at > utcnow()  # still advanced


def test_stale_schedule_with_catch_up_on_fires(db, settings_row, device_row, action_row):
    settings_row.catch_up_missed = True
    now = utcnow()
    schedule = _make_schedule(
        db, device_row, action_row, next_run_at=now - dt.timedelta(hours=2)
    )
    db.commit()

    scheduler.tick()

    db.refresh(schedule)
    executions = db.query(ScheduleExecution).filter_by(schedule_id=schedule.id).all()
    assert len(executions) == 1
    assert executions[0].overall_status == ExecutionStatus.SUCCESS.value


def test_not_yet_due_schedule_is_untouched(db, settings_row, device_row, action_row):
    future = utcnow() + dt.timedelta(hours=1)
    schedule = _make_schedule(db, device_row, action_row, next_run_at=future)
    db.commit()

    scheduler.tick()

    db.refresh(schedule)
    assert schedule.next_run_at == future
    assert db.query(ScheduleExecution).filter_by(schedule_id=schedule.id).count() == 0


def test_disabled_schedule_is_untouched_even_if_due(db, settings_row, device_row, action_row):
    overdue = utcnow() - dt.timedelta(seconds=5)
    schedule = _make_schedule(db, device_row, action_row, next_run_at=overdue, enabled=False)
    db.commit()

    scheduler.tick()

    db.refresh(schedule)
    assert schedule.next_run_at == overdue
    assert db.query(ScheduleExecution).filter_by(schedule_id=schedule.id).count() == 0


@pytest.mark.slow
def test_real_background_loop_fires_a_due_schedule_on_its_own(
    db, device_row, action_row, monkeypatch
):
    """Unlike the tests above, this goes through the real FastAPI
    lifespan and the actual asyncio task, not a direct tick() call,
    proving the wiring in app.main actually starts the loop."""
    monkeypatch.setattr(scheduler, "POLL_INTERVAL_SECONDS", 1)

    schedule = _make_schedule(
        db, device_row, action_row, next_run_at=utcnow() - dt.timedelta(seconds=2)
    )
    db.commit()
    schedule_id = schedule.id

    ensure_default_settings(db)

    from fastapi.testclient import TestClient

    from app.main import app

    async def run():
        with TestClient(app):
            await asyncio.sleep(3.5)

    asyncio.run(run())

    with SessionLocal() as fresh_db:
        executions = fresh_db.query(ScheduleExecution).filter_by(schedule_id=schedule_id).all()
        assert len(executions) >= 1
        assert executions[0].overall_status == ExecutionStatus.SUCCESS.value
