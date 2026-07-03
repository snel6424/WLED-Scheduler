"""Tests for the aggregate history endpoint: the one that serves the
standalone History tab, as opposed to GET /api/schedules/{id}/executions
which already existed for the per-schedule view.
"""

import datetime as dt

from app.models import ExecutionStatus, Schedule, ScheduleExecution, TriggerType, utcnow


def _make_execution(db, device, action, status=ExecutionStatus.SUCCESS, fired_at=None):
    schedule = Schedule(
        name="Dusk", devices=[device], action_id=action.id,
        trigger_type=TriggerType.SUNSET, offset_minutes=-10,
    )
    db.add(schedule)
    db.flush()
    execution = ScheduleExecution(
        schedule_id=schedule.id,
        device_results=[{"device_id": device.id, "status": status.value, "error_message": None}],
        fired_at=fired_at or utcnow(),
    )
    db.add(execution)
    db.commit()
    return schedule, execution


def test_history_entry_embeds_schedule_and_device_names(client, db, device, preset_action):
    from app.models import Action, Device

    device_row = db.get(Device, device["id"])
    action = db.get(Action, preset_action["id"])
    _make_execution(db, device_row, action)

    response = client.get("/api/history")
    assert response.status_code == 200
    entries = response.json()
    assert len(entries) == 1
    assert entries[0]["schedule"]["name"] == "Dusk"
    assert entries[0]["device_results"][0]["device"]["name"] == device["name"]
    assert entries[0]["overall_status"] == "success"


def test_history_filters_by_device(client, db, device, preset_action):
    from app.models import Action, Device

    device_a = db.get(Device, device["id"])
    device_b = Device(name="Other", host="9.9.9.9")
    action = db.get(Action, preset_action["id"])
    db.add(device_b)
    db.flush()
    _make_execution(db, device_a, action)
    _make_execution(db, device_b, action)

    response = client.get(f"/api/history?device_id={device_a.id}")
    assert response.status_code == 200
    assert len(response.json()) == 1
    assert response.json()[0]["device_results"][0]["device"]["name"] == "Porch"


def test_history_filters_by_date_range(client, db, device, preset_action):
    from app.models import Action, Device

    device_row = db.get(Device, device["id"])
    action = db.get(Action, preset_action["id"])
    _make_execution(db, device_row, action, fired_at=dt.datetime(2020, 1, 1))
    _make_execution(db, device_row, action, fired_at=utcnow())

    response = client.get("/api/history?since=2099-01-01T00:00:00")
    assert response.json() == []

    response = client.get("/api/history?until=2020-06-01T00:00:00")
    assert len(response.json()) == 1


def test_history_orders_most_recent_first(client, db, device, preset_action):
    from app.models import Action, Device

    device_row = db.get(Device, device["id"])
    action = db.get(Action, preset_action["id"])
    _make_execution(db, device_row, action, fired_at=dt.datetime(2020, 1, 1))
    _make_execution(db, device_row, action, fired_at=dt.datetime(2025, 1, 1))

    response = client.get("/api/history")
    fired_dates = [e["fired_at"] for e in response.json()]
    assert fired_dates == sorted(fired_dates, reverse=True)


def test_history_entry_embeds_action_for_preset_type(client, db, device, preset_action):
    from app.models import Action, Device

    device_row = db.get(Device, device["id"])
    action = db.get(Action, preset_action["id"])
    _make_execution(db, device_row, action)

    entry = client.get("/api/history").json()[0]
    assert entry["action"]["type"] == "preset"
    assert entry["action"]["payload"] == {"ps": 5}


def test_history_entry_embeds_action_for_state_type(client, db, device):
    from app.models import Action, ActionType, Device

    device_row = db.get(Device, device["id"])
    action = Action(name="Off", type=ActionType.STATE, payload={"on": False})
    db.add(action)
    db.flush()
    _make_execution(db, device_row, action)

    entry = client.get("/api/history").json()[0]
    assert entry["action"]["type"] == "state"
    assert entry["action"]["payload"]["on"] is False


def test_history_entry_shows_per_device_results_with_partial_overall_status(
    client, db, device, preset_action
):
    """One execution covering several devices is one history entry, not
    one per device, with a mixed-outcome overall_status of 'partial'."""
    from app.models import Action, Device

    device_a = db.get(Device, device["id"])
    device_b = Device(name="Lamp", host="9.9.9.8")
    db.add(device_b)
    db.flush()
    action = db.get(Action, preset_action["id"])

    schedule = Schedule(
        name="Dusk", devices=[device_a, device_b], action_id=action.id,
        trigger_type=TriggerType.SUNSET, offset_minutes=-10,
    )
    db.add(schedule)
    db.flush()
    db.add(
        ScheduleExecution(
            schedule_id=schedule.id,
            device_results=[
                {"device_id": device_a.id, "status": "success", "error_message": None},
                {"device_id": device_b.id, "status": "failed", "error_message": "timed out"},
            ],
        )
    )
    db.commit()

    entries = client.get("/api/history").json()
    assert len(entries) == 1
    assert entries[0]["overall_status"] == "partial"
    results = {r["device"]["name"]: r for r in entries[0]["device_results"]}
    assert results["Porch"]["status"] == "success"
    assert results["Lamp"]["status"] == "failed"
    assert results["Lamp"]["error_message"] == "timed out"


def test_history_entry_handles_since_deleted_device(client, db, device, preset_action):
    """device_results.device_id isn't a foreign key (it's embedded in
    JSON), so it can outlive the device it refers to; the API should
    still return the entry with device: null rather than erroring."""
    from app.models import Action, Device

    device_row = db.get(Device, device["id"])
    action = db.get(Action, preset_action["id"])
    _make_execution(db, device_row, action)

    db.delete(device_row)
    db.commit()

    entries = client.get("/api/history").json()
    assert len(entries) == 1
    assert entries[0]["device_results"][0]["device"] is None
