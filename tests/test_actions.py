"""Tests for the actions router. The payload-shape validation itself
is already covered in test_schemas.py; these focus on what's specific
to the router: persistence, and the delete-blocked-while-referenced
behavior at the HTTP layer.
"""


def test_create_and_get_action(client):
    created = client.post(
        "/api/actions", json={"name": "Movie mode", "type": "preset", "payload": {"ps": 5}}
    )
    assert created.status_code == 201
    action_id = created.json()["id"]

    fetched = client.get(f"/api/actions/{action_id}")
    assert fetched.status_code == 200
    assert fetched.json()["name"] == "Movie mode"


def test_patch_changing_type_without_matching_payload_is_422(client, preset_action):
    response = client.patch(f"/api/actions/{preset_action['id']}", json={"type": "state"})
    assert response.status_code == 422


def test_patch_unrelated_field_preserves_payload(client, preset_action):
    response = client.patch(
        f"/api/actions/{preset_action['id']}", json={"transition_ms": 500}
    )
    assert response.status_code == 200
    body = response.json()
    assert body["payload"] == {"ps": 5}
    assert body["transition_ms"] == 500


def test_delete_blocked_while_a_schedule_references_it(
    client, device, preset_action, configured_settings
):
    schedule = client.post(
        "/api/schedules",
        json={
            "name": "Dusk", "device_id": device["id"], "action_id": preset_action["id"],
            "trigger_type": "sunset", "offset_minutes": -10,
        },
    )
    assert schedule.status_code == 201

    response = client.delete(f"/api/actions/{preset_action['id']}")
    assert response.status_code == 409
    assert "Dusk" in response.json()["detail"]


def test_delete_succeeds_once_unreferenced(client, preset_action):
    response = client.delete(f"/api/actions/{preset_action['id']}")
    assert response.status_code == 204
