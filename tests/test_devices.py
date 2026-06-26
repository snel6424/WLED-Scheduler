"""Tests for the devices router, against the real mock WLED server
rather than mocking wled_client itself, so a regression in either
direction (the client or the router) would actually show up here.
"""


from tests.mock_wled import server as mock_wled_server


def test_create_device_pulls_real_info_from_the_device(client, mock_wled_host):
    response = client.post("/api/devices", json={"host": mock_wled_host})
    assert response.status_code == 201
    body = response.json()
    assert body["name"] == "Test Light"
    assert body["mac"] == "aabbccddeeff"
    assert body["capabilities"]["led_count"] == 30
    assert body["capabilities"]["wifi_signal_percent"] == 88
    assert body["capabilities"]["version"] == "0.14.0"


def test_create_device_uses_explicit_name_over_wled_name(client, mock_wled_host):
    response = client.post("/api/devices", json={"name": "Lamp", "host": mock_wled_host})
    assert response.status_code == 201
    assert response.json()["name"] == "Lamp"


def test_create_device_requires_name_if_wled_info_has_no_name(client, mock_wled_host, monkeypatch):
    monkeypatch.setitem(mock_wled_server.INFO, "name", "")
    response = client.post("/api/devices", json={"host": mock_wled_host})
    assert response.status_code == 422
    assert "name" in response.json()["detail"].lower()


def test_duplicate_host_rejected(client, device, mock_wled_host):
    response = client.post("/api/devices", json={"name": "Porch 2", "host": mock_wled_host})
    assert response.status_code == 409


def test_unreachable_device_rejected(client):
    response = client.post("/api/devices", json={"name": "Nowhere", "host": "127.0.0.1:1"})
    assert response.status_code == 422


def test_presets_are_normalized_sorted_and_exclude_id_zero(client, device):
    response = client.get(f"/api/devices/{device['id']}/presets")
    assert response.status_code == 200
    assert response.json() == [
        {"id": 1, "name": "Warm Glow"},
        {"id": 5, "name": "Movie Night"},
    ]


def test_get_nonexistent_device_is_404(client):
    response = client.get("/api/devices/does-not-exist")
    assert response.status_code == 404


def test_delete_device_then_404_on_refetch(client, device):
    response = client.delete(f"/api/devices/{device['id']}")
    assert response.status_code == 204
    assert client.get(f"/api/devices/{device['id']}").status_code == 404


def test_create_device_with_room(client, mock_wled_host):
    response = client.post(
        "/api/devices", json={"name": "Lamp", "host": mock_wled_host, "room": "Office"}
    )
    assert response.status_code == 201
    assert response.json()["room"] == "Office"


def test_create_device_without_room_defaults_to_none(client, device):
    assert device["room"] is None


def test_rename_and_set_room(client, device):
    response = client.patch(
        f"/api/devices/{device['id']}", json={"name": "New Name", "room": "Garage"}
    )
    assert response.status_code == 200
    assert response.json()["name"] == "New Name"
    assert response.json()["room"] == "Garage"


def test_device_never_seen_reads_offline(client, device):
    # The `device` fixture creates via the API, which does set last_seen_at
    # implicitly? No: creation doesn't call refresh, so it starts unseen.
    assert client.get(f"/api/devices/{device['id']}").json()["online"] is False


def test_device_recently_refreshed_reads_online(client, device):
    refreshed = client.post(f"/api/devices/{device['id']}/refresh")
    assert refreshed.json()["online"] is True


def test_device_stale_last_seen_reads_offline(client, device, db):
    import datetime

    from app.models import Device, utcnow

    row = db.get(Device, device["id"])
    row.last_seen_at = utcnow() - datetime.timedelta(hours=5)
    db.commit()
    assert client.get(f"/api/devices/{device['id']}").json()["online"] is False
