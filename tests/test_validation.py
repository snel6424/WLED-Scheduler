"""Tests for app.validation: the merge-then-revalidate functions that
close the partial-update gap a PATCH body alone can't catch on its
own (changing only `type` without `payload`, or only `trigger_type`
without clearing the now-irrelevant field).
"""

import datetime as dt

import pytest
from pydantic import ValidationError

from app.models import Action, ActionType, Device, Schedule, TriggerType
from app.schemas import ActionUpdate, ScheduleUpdate
from app.validation import merge_and_validate_action, merge_and_validate_schedule


def _action(**overrides):
    base = dict(name="Movie mode", type=ActionType.PRESET, payload={"ps": 5}, transition_ms=None)
    base.update(overrides)
    return Action(**base)


def _schedule(**overrides):
    # Not persisted, so `devices` is populated directly with unattached
    # Device instances rather than via device_ids: merge_and_validate_schedule
    # only reads existing.devices' ids, it never hits the database.
    base = dict(
        name="Morning", devices=[Device(id="d1")], action_id="a1", trigger_type=TriggerType.TIME,
        time_of_day=dt.time(7, 0), offset_minutes=None, days_of_week=127, enabled=True,
    )
    base.update(overrides)
    return Schedule(**base)


def test_changing_action_type_without_matching_payload_is_rejected():
    with pytest.raises(ValidationError):
        merge_and_validate_action(_action(), ActionUpdate(type=ActionType.STATE))


def test_changing_action_type_and_payload_together_is_accepted():
    result = merge_and_validate_action(
        _action(), ActionUpdate(type=ActionType.STATE, payload={"on": True, "bri": 200})
    )
    assert result.type == ActionType.STATE
    assert result.payload == {"on": True, "bri": 200}


def test_changing_unrelated_action_field_preserves_type_and_payload():
    result = merge_and_validate_action(_action(), ActionUpdate(transition_ms=500))
    assert result.type == ActionType.PRESET
    assert result.payload == {"ps": 5}
    assert result.transition_ms == 500


def test_switching_trigger_type_without_clearing_old_field_is_rejected():
    with pytest.raises(ValidationError):
        merge_and_validate_schedule(
            _schedule(), ScheduleUpdate(trigger_type=TriggerType.SUNSET, offset_minutes=-10)
        )


def test_switching_trigger_type_and_clearing_old_field_is_accepted():
    result = merge_and_validate_schedule(
        _schedule(),
        ScheduleUpdate(trigger_type=TriggerType.SUNSET, offset_minutes=-10, time_of_day=None),
    )
    assert result.trigger_type == TriggerType.SUNSET
    assert result.offset_minutes == -10
    assert result.time_of_day is None


def test_changing_unrelated_schedule_field_preserves_trigger_fields():
    result = merge_and_validate_schedule(_schedule(), ScheduleUpdate(name="Morning v2"))
    assert result.name == "Morning v2"
    assert result.trigger_type == TriggerType.TIME
    assert result.time_of_day == dt.time(7, 0)
