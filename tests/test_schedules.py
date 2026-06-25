"""Tests for the schedules router: next_run_at computation on create,
the location-required guard, the recompute-on-trigger-change behavior,
and run-now actually firing against the mock device.
"""


def test_sunset_schedule_rejected_before_location_is_configured(client, device, preset_action):
    response = client.post(
        "/api/schedules",
        json={
            "name": "Dusk", "device_id": device["id"], "action_id": preset_action["id"],
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
            "name": "Dusk", "device_id": device["id"], "action_id": preset_action["id"],
            "trigger_type": "sunset", "offset_minutes": -10,
        },
    )
    assert response.status_code == 201
    assert response.json()["next_run_at"] is not None


def test_create_with_unknown_device_is_404(client, preset_action, configured_settings):
    response = client.post(
        "/api/schedules",
        json={
            "name": "Dusk", "device_id": "does-not-exist", "action_id": preset_action["id"],
            "trigger_type": "sunset", "offset_minutes": -10,
        },
    )
    assert response.status_code == 404


def test_switching_trigger_type_without_clearing_old_field_is_422(
    client, device, preset_action, configured_settings
):
    created = client.post(
        "/api/schedules",
        json={
            "name": "Morning", "device_id": device["id"], "action_id": preset_action["id"],
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
            "name": "Dusk", "device_id": device["id"], "action_id": preset_action["id"],
            "trigger_type": "sunset", "offset_minutes": -10,
        },
    )
    schedule_id = created.json()["id"]

    response = client.post(f"/api/schedules/{schedule_id}/run-now")
    assert response.status_code == 200
    assert response.json()["status"] == "success"

    history = client.get(f"/api/schedules/{schedule_id}/executions")
    assert len(history.json()) == 1

    refetched = client.get(f"/api/schedules/{schedule_id}")
    assert refetched.json()["last_run_at"] is not None


def test_run_now_works_even_when_disabled(client, device, preset_action, configured_settings):
    created = client.post(
        "/api/schedules",
        json={
            "name": "Dusk", "device_id": device["id"], "action_id": preset_action["id"],
            "trigger_type": "sunset", "offset_minutes": -10, "enabled": False,
        },
    )
    schedule_id = created.json()["id"]

    response = client.post(f"/api/schedules/{schedule_id}/run-now")
    assert response.status_code == 200
    assert response.json()["status"] == "success"


def test_device_delete_cascades_to_schedule(client, device, preset_action, configured_settings):
    created = client.post(
        "/api/schedules",
        json={
            "name": "Dusk", "device_id": device["id"], "action_id": preset_action["id"],
            "trigger_type": "sunset", "offset_minutes": -10,
        },
    )
    schedule_id = created.json()["id"]

    client.delete(f"/api/devices/{device['id']}")

    assert client.get(f"/api/schedules/{schedule_id}").status_code == 404
