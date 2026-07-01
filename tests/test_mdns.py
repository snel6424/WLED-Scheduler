"""Tests for app.mdns: the logic that replaced app.device_health
entirely (see CLAUDE.md for why). These deliberately don't stand up a
real multicast socket -- MDNS_ENABLED=false in conftest.py keeps the
`client` fixture from doing that on every test -- and instead exercise
the pure matching/debounce logic the real listener calls into,
substituting a fake `is_hostname_live` for what would otherwise be a
zeroconf cache lookup.
"""

from app import mdns
from app.models import Device


def test_strip_local_suffix_handles_trailing_dot_and_bare_local():
    assert mdns.strip_local_suffix("porch.local.") == "porch"
    assert mdns.strip_local_suffix("porch.local") == "porch"


def test_to_fqdn_round_trips_with_strip_local_suffix():
    assert mdns.strip_local_suffix(mdns.to_fqdn("porch")) == "porch"


def test_strip_port():
    assert mdns.strip_port("192.168.1.50:8080") == "192.168.1.50"
    assert mdns.strip_port("192.168.1.50") == "192.168.1.50"


def test_match_device_by_hostname():
    a = Device(name="A", host="10.0.0.1", mdns_name="porch")
    b = Device(name="B", host="10.0.0.2", mdns_name="kitchen")
    assert mdns.match_device_by_hostname("kitchen", [a, b]) is b
    assert mdns.match_device_by_hostname("missing", [a, b]) is None


def test_match_device_by_ip_skips_devices_that_already_have_an_mdns_name():
    a = Device(name="A", host="10.0.0.1")
    b = Device(name="B", host="10.0.0.2", mdns_name="kitchen")
    assert mdns.match_device_by_ip("10.0.0.1", [a, b]) is a
    # Hostname is authoritative once known; IP matching is only the
    # manual-add-before-mDNS-ever-saw-it fallback.
    assert mdns.match_device_by_ip("10.0.0.2", [a, b]) is None


def test_mark_online_sets_state_and_last_seen(db):
    device = Device(name="Porch", host="10.0.0.1")
    db.add(device)
    db.commit()

    mdns.mark_online(db, device, ip="10.0.0.1", mdns_name="porch")
    db.commit()

    assert mdns.is_online(device.id) is True
    db.refresh(device)
    assert device.last_seen_at is not None


def test_mark_online_backfills_mdns_name_for_a_device_added_by_ip(db):
    device = Device(name="Porch", host="10.0.0.1")
    db.add(device)
    db.commit()

    mdns.mark_online(db, device, ip="10.0.0.1", mdns_name="porch")
    db.commit()

    db.refresh(device)
    assert device.mdns_name == "porch"


def test_mark_online_updates_ip_on_dhcp_reassignment_preserving_port(db):
    device = Device(name="Porch", host="10.0.0.1:8080", mdns_name="porch")
    db.add(device)
    db.commit()

    mdns.mark_online(db, device, ip="10.0.0.99", mdns_name="porch")
    db.commit()

    db.refresh(device)
    assert device.host == "10.0.0.99:8080"


def test_mark_offline_immediate_bypasses_debounce(db):
    device = Device(name="Porch", host="10.0.0.1", mdns_name="porch")
    db.add(device)
    db.commit()
    mdns.mark_online(db, device, ip="10.0.0.1", mdns_name="porch")
    db.commit()
    assert mdns.is_online(device.id) is True

    mdns.mark_offline_immediate(db, device)
    db.commit()

    assert mdns.is_online(device.id) is False


def test_is_online_defaults_false_for_a_device_never_seen():
    assert mdns.is_online("never-seen-device-id") is False


def test_sweep_tick_requires_two_consecutive_misses_before_offline(db, monkeypatch):
    device = Device(name="Porch", host="10.0.0.1", mdns_name="porch")
    db.add(device)
    db.commit()
    mdns.mark_online(db, device, ip="10.0.0.1", mdns_name="porch")
    db.commit()

    monkeypatch.setattr(mdns, "is_hostname_live", lambda zc, mdns_name, now_ms: False)

    mdns.sweep_tick(object())
    assert mdns.is_online(device.id) is True, "a single missed cycle must not flip it offline"

    mdns.sweep_tick(object())
    assert mdns.is_online(device.id) is False, "a second consecutive miss must flip it offline"


def test_sweep_tick_resets_miss_counter_once_the_record_is_live_again(db, monkeypatch):
    device = Device(name="Porch", host="10.0.0.1", mdns_name="porch")
    db.add(device)
    db.commit()
    mdns.mark_online(db, device, ip="10.0.0.1", mdns_name="porch")
    db.commit()

    live = {"value": False}
    monkeypatch.setattr(mdns, "is_hostname_live", lambda zc, mdns_name, now_ms: live["value"])

    mdns.sweep_tick(object())  # miss 1

    live["value"] = True
    mdns.sweep_tick(object())  # live again -- counter should reset to 0

    live["value"] = False
    mdns.sweep_tick(object())  # miss 1 again, not 2 in a row

    assert mdns.is_online(device.id) is True


def test_sweep_tick_ignores_devices_with_no_mdns_name(db, monkeypatch):
    """Nothing to check for a device app.mdns has never matched --
    manually added by IP and never confirmed by mDNS. It just reads
    offline, same as if it had never been seen at all."""
    device = Device(name="Manual", host="10.0.0.5")
    db.add(device)
    db.commit()

    calls = []
    monkeypatch.setattr(
        mdns, "is_hostname_live", lambda zc, mdns_name, now_ms: calls.append(mdns_name) or False
    )

    mdns.sweep_tick(object())

    assert calls == []
    assert mdns.is_online(device.id) is False
