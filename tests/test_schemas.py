"""Tests for app.schemas: payload shape validation and the
trigger-type cross-field rules, independent of any database or API.
"""

import pytest
from pydantic import ValidationError

from app.models import ActionType, TriggerType
from app.schemas import ActionCreate, ScheduleCreate


def test_preset_action_payload_is_valid():
    action = ActionCreate(name="Movie mode", type=ActionType.PRESET, payload={"ps": 5})
    assert action.payload == {"ps": 5}


def test_state_action_payload_is_valid():
    action = ActionCreate(
        name="Warm white", type=ActionType.STATE,
        payload={"on": True, "bri": 180, "seg": [{"col": [[255, 140, 40]], "fx": 0, "pal": 0}]},
    )
    assert action.payload["bri"] == 180


def test_state_payload_rejects_speed_and_intensity_out_of_v1_scope():
    """sx/ix were explicitly left out of the agreed v1 feature cut.
    extra="forbid" on the payload sub-schemas is what actually enforces
    that boundary, rather than it only living in a planning note."""
    with pytest.raises(ValidationError):
        ActionCreate(name="Bad", type=ActionType.STATE, payload={"seg": [{"sx": 128, "ix": 64}]})


def test_preset_payload_requires_ps():
    with pytest.raises(ValidationError):
        ActionCreate(name="Bad", type=ActionType.PRESET, payload={})


def test_state_payload_rejected_for_preset_type():
    with pytest.raises(ValidationError):
        ActionCreate(name="Bad", type=ActionType.PRESET, payload={"on": True})


def test_time_trigger_requires_time_of_day():
    with pytest.raises(ValidationError):
        ScheduleCreate(
            name="Bad", device_ids=["d1"], action_id="a1", trigger_type=TriggerType.TIME
        )


def test_time_trigger_rejects_offset_minutes():
    with pytest.raises(ValidationError):
        ScheduleCreate(
            name="Bad", device_ids=["d1"], action_id="a1", trigger_type=TriggerType.TIME,
            time_of_day="07:00:00", offset_minutes=-10,
        )


def test_sunset_trigger_requires_offset_minutes():
    with pytest.raises(ValidationError):
        ScheduleCreate(
            name="Bad", device_ids=["d1"], action_id="a1", trigger_type=TriggerType.SUNSET
        )


def test_sunset_trigger_rejects_time_of_day():
    with pytest.raises(ValidationError):
        ScheduleCreate(
            name="Bad", device_ids=["d1"], action_id="a1", trigger_type=TriggerType.SUNSET,
            time_of_day="19:00:00",
        )


def test_valid_sunset_schedule():
    schedule = ScheduleCreate(
        name="Dusk", device_ids=["d1"], action_id="a1", trigger_type=TriggerType.SUNSET,
        offset_minutes=-10,
    )
    assert schedule.offset_minutes == -10
    assert schedule.time_of_day is None


def test_days_of_week_out_of_range_rejected():
    with pytest.raises(ValidationError):
        ScheduleCreate(
            name="Bad", device_ids=["d1"], action_id="a1", trigger_type=TriggerType.TIME,
            time_of_day="07:00:00", days_of_week=200,
        )
