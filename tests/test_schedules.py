"""Tests for the schedules router: next_run_at computation on create,
the location-required guard, the recompute-on-trigger-change behavior,
and run-now actually firing against the mock device.
"""


def test_sunset_schedule_rejected_before_location_is_configured(client, device, preset_action):
    response = client.post(
        "/api/schedules",
        json={
            "name": "Dusk", "device_ids": [device["id"]], "action_id": preset_action["id"],
            "trigger_type": "sunset", "offset_minutes": -10,
        },
    )
    assert response.status_code == 422


def test_sunset_schedule_created_after_location_is_set(
    client, device, preset_action, configured_settings
):
    response = client.post(
        "/api/schedules",
        json={
            "name": "Dusk", "device_ids": [device["id"]], "action_id": preset_action["id"],
            "trigger_type": "sunset", "offset_minutes": -10,
        },
    )
    assert response.status_code == 201
    assert response.json()["next_run_at"] is not None


def test_create_with_unknown_device_is_404(client, preset_action, configured_settings):
    response = client.post(
        "/api/schedules",
        json={
            "name": "Dusk", "device_ids": ["does-not-exist"], "action_id": preset_action["id"],
            "trigger_type": "sunset", "offset_minutes": -10,
        },
    )
    assert response.status_code == 404


def test_create_schedule_rejects_invalid_date_range(client, device, preset_action, configured_settings):
    response = client.post(
        "/api/schedules",
        json={
            "name": "Future", "device_ids": [device["id"]], "action_id": preset_action["id"],
            "trigger_type": "time", "time_of_day": "07:00:00",
            "start_date": "2026-06-26", "end_date": "2026-06-25",
        },
    )
    assert response.status_code == 422


def test_update_schedule_rejects_invalid_date_range(client, device, preset_action, configured_settings):
    created = client.post(
        "/api/schedules",
        json={
            "name": "Morning", "device_ids": [device["id"]], "action_id": preset_action["id"],
            "trigger_type": "time", "time_of_day": "07:00:00",
            "start_date": "2026-06-25", "end_date": "2026-06-26",
        },
    )
    schedule_id = created.json()["id"]

    response = client.patch(
        f"/api/schedules/{schedule_id}",
        json={"start_date": "2026-06-27", "end_date": "2026-06-26"},
    )
    assert response.status_code == 422


def test_switching_trigger_type_without_clearing_old_field_is_422(
    client, device, preset_action, configured_settings
):
    created = client.post(
        "/api/schedules",
        json={
            "name": "Morning", "device_ids": [device["id"]], "action_id": preset_action["id"],
            "trigger_type": "time", "time_of_day": "07:00:00", "days_of_week": 127,
        },
    )
    schedule_id = created.json()["id"]

    response = client.patch(
        f"/api/schedules/{schedule_id}", json={"trigger_type": "sunset", "offset_minutes": -10}
    )
    assert response.status_code == 422


def test_run_now_fires_and_logs_execution(client, device, preset_action, configured_settings):
    created = client.post(
        "/api/schedules",
        json={
            "name": "Dusk", "device_ids": [device["id"]], "action_id": preset_action["id"],
            "trigger_type": "sunset", "offset_minutes": -10,
        },
    )
    schedule_id = created.json()["id"]

    response = client.post(f"/api/schedules/{schedule_id}/run-now")
    assert response.status_code == 200
    body = response.json()
    assert body["overall_status"] == "success"
    assert len(body["device_results"]) == 1
    assert body["device_results"][0]["device"]["id"] == device["id"]
    assert body["device_results"][0]["status"] == "success"

    history = client.get(f"/api/schedules/{schedule_id}/executions")
    assert len(history.json()) == 1

    refetched = client.get(f"/api/schedules/{schedule_id}")
    assert refetched.json()["last_run_at"] is not None


def test_run_now_works_even_when_disabled(client, device, preset_action, configured_settings):
    created = client.post(
        "/api/schedules",
        json={
            "name": "Dusk", "device_ids": [device["id"]], "action_id": preset_action["id"],
            "trigger_type": "sunset", "offset_minutes": -10, "enabled": False,
        },
    )
    schedule_id = created.json()["id"]

    response = client.post(f"/api/schedules/{schedule_id}/run-now")
    assert response.status_code == 200
    assert response.json()["overall_status"] == "success"


def test_create_schedule_with_multiple_devices(client, device, preset_action, configured_settings):
    from tests.mock_wled import server as mock_wled

    _, port = mock_wled.start()
    other = client.post("/api/devices", json={"name": "Lamp", "host": f"127.0.0.1:{port}"})
    assert other.status_code == 201
    other_id = other.json()["id"]

    created = client.post(
        "/api/schedules",
        json={
            "name": "Dusk", "action_id": preset_action["id"],
            "device_ids": [device["id"], other_id],
            "trigger_type": "sunset", "offset_minutes": -10,
        },
    )
    assert created.status_code == 201
    device_ids = {d["id"] for d in created.json()["devices"]}
    assert device_ids == {device["id"], other_id}


def test_create_schedule_requires_at_least_one_device(client, preset_action, configured_settings):
    response = client.post(
        "/api/schedules",
        json={
            "name": "Dusk", "device_ids": [], "action_id": preset_action["id"],
            "trigger_type": "sunset", "offset_minutes": -10,
        },
    )
    assert response.status_code == 422


def test_create_schedule_with_one_invalid_device_id_is_404(
    client, device, preset_action, configured_settings
):
    response = client.post(
        "/api/schedules",
        json={
            "name": "Dusk", "device_ids": [device["id"], "does-not-exist"],
            "action_id": preset_action["id"], "trigger_type": "sunset", "offset_minutes": -10,
        },
    )
    assert response.status_code == 404


def test_update_schedule_changes_device_set(client, device, preset_action, configured_settings):
    from tests.mock_wled import server as mock_wled

    _, port = mock_wled.start()
    other = client.post("/api/devices", json={"name": "Lamp", "host": f"127.0.0.1:{port}"})
    other_id = other.json()["id"]

    created = client.post(
        "/api/schedules",
        json={
            "name": "Dusk", "device_ids": [device["id"]], "action_id": preset_action["id"],
            "trigger_type": "sunset", "offset_minutes": -10,
        },
    )
    schedule_id = created.json()["id"]

    response = client.patch(f"/api/schedules/{schedule_id}", json={"device_ids": [other_id]})
    assert response.status_code == 200
    assert [d["id"] for d in response.json()["devices"]] == [other_id]


def test_run_now_reports_partial_when_one_device_is_unreachable(
    client, db, device, preset_action, configured_settings
):
    from app.models import Device

    bad_device = Device(name="Unreachable", host="127.0.0.1:1")
    db.add(bad_device)
    db.commit()

    created = client.post(
        "/api/schedules",
        json={
            "name": "Dusk", "device_ids": [device["id"], bad_device.id],
            "action_id": preset_action["id"], "trigger_type": "sunset", "offset_minutes": -10,
        },
    )
    schedule_id = created.json()["id"]

    response = client.post(f"/api/schedules/{schedule_id}/run-now")
    assert response.status_code == 200
    body = response.json()
    assert body["overall_status"] == "partial"
    statuses = {r["device"]["name"]: r["status"] for r in body["device_results"]}
    assert statuses["Porch"] == "success"
    assert statuses["Unreachable"] == "failed"


def test_device_delete_removes_it_from_schedule_without_deleting_schedule(
    client, device, preset_action, configured_settings
):
    """A device can now target several devices; deleting just one of
    them should shrink the schedule's device list rather than delete
    the whole schedule out from under the remaining device(s)."""
    from tests.mock_wled import server as mock_wled

    _, port = mock_wled.start()
    other = client.post("/api/devices", json={"name": "Lamp", "host": f"127.0.0.1:{port}"})
    other_id = other.json()["id"]

    created = client.post(
        "/api/schedules",
        json={
            "name": "Dusk", "action_id": preset_action["id"],
            "device_ids": [device["id"], other_id],
            "trigger_type": "sunset", "offset_minutes": -10,
        },
    )
    schedule_id = created.json()["id"]

    client.delete(f"/api/devices/{device['id']}")

    refetched = client.get(f"/api/schedules/{schedule_id}")
    assert refetched.status_code == 200
    assert [d["id"] for d in refetched.json()["devices"]] == [other_id]
