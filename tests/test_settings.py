"""Tests for the settings router. The one real piece of logic here is
blocking a location clear that would orphan a sunrise/sunset schedule.
"""


def test_settings_bootstrapped_and_starts_unconfigured(client):
    response = client.get("/api/settings")
    assert response.status_code == 200
    assert response.json()["latitude"] is None


def test_patch_configures_location(client):
    response = client.patch(
        "/api/settings",
        json={"latitude": 35.4676, "longitude": -97.5164, "timezone": "America/Chicago"},
    )
    assert response.status_code == 200
    assert response.json()["latitude"] == 35.4676


def test_clearing_latitude_blocked_while_sunset_schedule_exists(
    client, device, preset_action, configured_settings
):
    schedule = client.post(
        "/api/schedules",
        json={
            "name": "Dusk", "device_ids": [device["id"]], "action_id": preset_action["id"],
            "trigger_type": "sunset", "offset_minutes": -10,
        },
    )
    assert schedule.status_code == 201

    response = client.patch("/api/settings", json={"latitude": None})
    assert response.status_code == 409
    assert "Dusk" in response.json()["detail"]


def test_clearing_latitude_allowed_once_no_sun_schedules_exist(client, configured_settings):
    response = client.patch("/api/settings", json={"latitude": None})
    assert response.status_code == 200


def test_setting_fields_one_at_a_time_never_blocked_before_location_was_ever_complete(client, db):
    """Regression test: the guard used to compare against the current
    state regardless of whether it was ever actually configured, which
    meant ANY settings save (even an unrelated one like timezone) would
    get blocked if latitude/longitude happened to already be null and a
    sunrise/sunset schedule existed (only reachable via direct DB
    access, not the real API, but worth guarding against regardless).
    """
    from app.models import Action, ActionType, Device, Schedule, TriggerType

    device = Device(name="Porch", host="1.2.3.4")
    action = Action(name="Glow", type=ActionType.PRESET, payload={"ps": 1})
    db.add_all([device, action])
    db.flush()
    db.add(
        Schedule(
            name="Dusk", devices=[device], action_id=action.id,
            trigger_type=TriggerType.SUNSET, offset_minutes=-10,
        )
    )
    db.commit()

    # Saving latitude alone, with longitude still unset, must not be blocked
    response = client.patch("/api/settings", json={"latitude": 35.4676})
    assert response.status_code == 200

    # Neither should an unrelated field, with location still incomplete
    response = client.patch("/api/settings", json={"catch_up_missed": True})
    assert response.status_code == 200
