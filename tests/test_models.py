"""Tests against the models directly, no API involved. These exist to
catch exactly the kind of thing that looks right on a read-through but
isn't: enum storage, cascade behavior, and CHECK constraints only show
their real behavior against an actual database.
"""

import datetime as dt

import pytest
from sqlalchemy import text
from sqlalchemy.exc import IntegrityError

from app.models import (
    Action,
    ActionType,
    Device,
    ExecutionStatus,
    Schedule,
    ScheduleExecution,
    Settings,
    TriggerType,
    utcnow,
)


def _device_and_action(db):
    device = Device(name="Porch", host="192.168.1.50")
    action = Action(name="Glow", type=ActionType.STATE, payload={"on": True})
    db.add_all([device, action])
    db.flush()
    return device, action


def test_enums_store_lowercase_value_not_member_name(db):
    """Without values_callable on the Enum columns, SQLAlchemy stores
    the member NAME ("SUNSET") rather than its value ("sunset"), which
    would silently break every CheckConstraint that compares against
    the lowercase string."""
    device, action = _device_and_action(db)
    schedule = Schedule(
        name="Dusk", device_id=device.id, action_id=action.id,
        trigger_type=TriggerType.SUNSET, offset_minutes=-10,
    )
    db.add(schedule)
    db.commit()

    raw = db.execute(
        text("SELECT trigger_type FROM schedules WHERE id = :id"), {"id": schedule.id}
    ).fetchone()
    assert raw[0] == "sunset"


def test_device_delete_cascades_to_schedule_and_execution(db):
    device, action = _device_and_action(db)
    schedule = Schedule(
        name="Dusk", device_id=device.id, action_id=action.id,
        trigger_type=TriggerType.SUNSET, offset_minutes=-10,
    )
    db.add(schedule)
    db.flush()
    execution = ScheduleExecution(
        schedule_id=schedule.id, device_id=device.id, status=ExecutionStatus.SUCCESS
    )
    db.add(execution)
    db.commit()
    schedule_id, execution_id = schedule.id, execution.id

    db.delete(device)
    db.commit()

    # passive_deletes=True means this session never issues a DELETE for
    # the Schedule/ScheduleExecution rows itself; it relies entirely on
    # SQLite's own ON DELETE CASCADE. That also means this session's
    # identity map has no idea they're gone and will happily hand back
    # the stale in-memory objects on db.get() without re-querying.
    # expire_all() forces a real read; a fresh session would work too.
    db.expire_all()

    assert db.get(Schedule, schedule_id) is None
    assert db.get(ScheduleExecution, execution_id) is None


def test_action_delete_blocked_while_schedule_references_it(db):
    device, action = _device_and_action(db)
    schedule = Schedule(
        name="Dusk", device_id=device.id, action_id=action.id,
        trigger_type=TriggerType.SUNSET, offset_minutes=-10,
    )
    db.add(schedule)
    db.commit()

    db.delete(action)
    with pytest.raises(IntegrityError):
        db.commit()
    db.rollback()


@pytest.mark.parametrize(
    "kwargs",
    [
        # trigger_type=time with no time_of_day
        dict(trigger_type=TriggerType.TIME),
        # sunrise/sunset with no offset_minutes
        dict(trigger_type=TriggerType.SUNRISE),
        # days_of_week out of range
        dict(trigger_type=TriggerType.TIME, time_of_day=dt.time(7, 0), days_of_week=200),
    ],
)
def test_schedule_check_constraints_reject_invalid_combinations(db, kwargs):
    device, action = _device_and_action(db)
    schedule = Schedule(name="Bad", device_id=device.id, action_id=action.id, **kwargs)
    db.add(schedule)
    with pytest.raises(IntegrityError):
        db.commit()
    db.rollback()


def test_known_gap_time_trigger_with_offset_minutes_not_rejected_at_db_level(db):
    """Documents a real, current gap rather than hiding it. The DB
    CheckConstraints only enforce "the right field is present", not
    "the wrong field is absent": ck_schedule_sun_requires_offset reads
    (trigger_type = 'time') OR (offset_minutes IS NOT NULL), which
    is satisfied whenever trigger_type IS 'time', regardless of
    whether offset_minutes also happens to be set. The Pydantic schema
    layer (test_schemas.py::test_time_trigger_rejects_offset_minutes)
    does catch this; the database does not. Accepted gap for now since
    everything goes through the API in practice; revisit if a second
    write path to this table is ever added."""
    device, action = _device_and_action(db)
    schedule = Schedule(
        name="Both set", device_id=device.id, action_id=action.id,
        trigger_type=TriggerType.TIME, time_of_day=dt.time(7, 0), offset_minutes=-10,
    )
    db.add(schedule)
    db.commit()  # does NOT raise today; that's the point of this test


def test_action_type_check_constraint_rejects_invalid_value(db):
    """Action.type's CheckConstraint was added after discovering
    sa.Enum doesn't create one on its own in SQLite (confirmed by
    inspecting the actual CREATE TABLE SQL). This test exists
    specifically to make sure that doesn't regress."""
    device = Device(name="Porch", host="192.168.1.50")
    db.add(device)
    db.flush()
    with pytest.raises(IntegrityError):
        # SQLite validates CHECK constraints at statement execution,
        # not at commit; the error happens right here, not below.
        db.execute(
            text(
                "INSERT INTO actions (id, name, type, payload, created_at, updated_at) "
                "VALUES ('bad-1', 'Bad', 'bogus', '{}', :now, :now)"
            ),
            {"now": utcnow()},
        )
    db.rollback()


def test_schedule_execution_status_check_constraint_rejects_invalid_value(db):
    device, action = _device_and_action(db)
    db.commit()
    with pytest.raises(IntegrityError):
        db.execute(
            text(
                "INSERT INTO schedule_executions (id, schedule_id, device_id, fired_at, status) "
                "VALUES ('bad-1', :sid, :did, :now, 'bogus')"
            ),
            {"sid": "nonexistent", "did": device.id, "now": utcnow()},
        )
    db.rollback()


def test_schedule_execution_accepts_skipped_status(db):
    device, action = _device_and_action(db)
    schedule = Schedule(
        name="Dusk", device_id=device.id, action_id=action.id,
        trigger_type=TriggerType.SUNSET, offset_minutes=-10,
    )
    db.add(schedule)
    db.flush()
    db.add(
        ScheduleExecution(
            schedule_id=schedule.id, device_id=device.id, status=ExecutionStatus.SKIPPED
        )
    )
    db.commit()  # should not raise


def test_settings_singleton_constraint_rejects_a_second_row(db):
    db.add(Settings(id=1))
    db.commit()
    db.add(Settings(id=2))
    with pytest.raises(IntegrityError):
        db.commit()
    db.rollback()
