"""Tests for app.device_health: the loop that keeps last_seen_at
honest, which the online/offline status shown in the UI derives from.
"""

from app import device_health
from app.models import Device


def test_tick_updates_last_seen_at_for_reachable_device(db, mock_wled_host):
    device = Device(name="Porch", host=mock_wled_host)
    db.add(device)
    db.commit()

    device_health.tick()

    db.refresh(device)
    assert device.last_seen_at is not None


def test_tick_leaves_unreachable_device_untouched(db):
    device = Device(name="Ghost", host="127.0.0.1:1")
    db.add(device)
    db.commit()

    device_health.tick()

    db.refresh(device)
    assert device.last_seen_at is None
