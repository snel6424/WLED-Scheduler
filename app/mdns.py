"""mDNS-based device discovery and reachability tracking.

Replaces the old HTTP-polling device health check entirely, per a
deliberate reversal of the original "HTTP reachability checks, not
mDNS or ICMP" v1 decision (see CLAUDE.md). WLED devices advertise
themselves via DNS-SD as `_wled._tcp.local.`, confirmed via a real
packet capture rather than assumed from documentation, and also
advertise the generic `_http._tcp.local.` alongside it, so every
browse in this module filters specifically for the WLED service type.

This module owns two things:

- `scan()`: a bounded, one-shot browse used by the add-device flow to
  surface devices not yet added. Independent of the persistent
  listener below, it opens and closes its own AsyncZeroconf.
- `start()` / `stop()`: a persistent listener, started once from
  app.main's lifespan, that keeps every known device's online status
  current for as long as the app runs.

Two genuinely different signals decide "a device just went offline",
and they're deliberately handled differently:

- A clean shutdown sends an mDNS goodbye packet: an unsolicited record
  update with TTL=0. That's a real packet, so it's handled the moment
  it's received, via a raw record-update listener watching A records
  directly -- offline immediately, no debounce.
- A power loss or network drop sends nothing at all. There's no packet
  to react to, so that case can't be made event-driven; it's the
  absence of a signal, which is inherently a timeout. A periodic sweep
  (well under WLED's 120s A/SRV record TTL) checks whether each
  tracked device's address record is still live in zeroconf's shared
  cache -- which the browser and goodbye listener below keep populated,
  so this makes no network calls of its own -- and only flips a device
  offline after 2 consecutive misses, to absorb a single dropped
  multicast packet without flapping the badge. This sweep is the one
  timer-driven piece of this module; everything else reacts to
  callbacks as records arrive.

Deliberately NOT used for offline detection: AsyncServiceBrowser's own
ServiceStateChange.Removed event. It's tied to the PTR record's TTL
(4500s / 75 minutes) and is only prompt when a goodbye happens to
un-announce the PTR too -- not a guarantee, and not the signal this
module is supposed to be watching per the underlying design decision.
"""

from __future__ import annotations

import asyncio
import logging
from dataclasses import dataclass, field

from sqlalchemy import select
from zeroconf import (
    RecordUpdateListener,
    ServiceStateChange,
    Zeroconf,
    current_time_millis,
)
from zeroconf import const as zc_const
from zeroconf.asyncio import AsyncServiceBrowser, AsyncServiceInfo, AsyncZeroconf

from app import config
from app.database import SessionLocal
from app.models import Device, utcnow

logger = logging.getLogger("app.mdns")

SERVICE_TYPE = "_wled._tcp.local."
RESOLVE_TIMEOUT_MS = 3000
SWEEP_INTERVAL_SECONDS = config.MDNS_SWEEP_INTERVAL_SECONDS
OFFLINE_MISS_THRESHOLD = config.MDNS_OFFLINE_MISS_THRESHOLD


def strip_local_suffix(hostname: str) -> str:
    """'porch.local.' -> 'porch'. Device.mdns_name is stored as the bare
    Bonjour hostname, without the trailing label, so it reads sensibly
    if ever shown in the UI and round-trips cleanly through to_fqdn."""
    return hostname.removesuffix(".").removesuffix(".local")


def to_fqdn(mdns_name: str) -> str:
    return f"{mdns_name}.local."


def strip_port(host: str) -> str:
    """Device.host is stored as `ip[:port]`, whatever was typed or
    discovered; only the address portion is comparable to a resolved
    mDNS A record."""
    if host.count(":") == 1:
        return host.rsplit(":", 1)[0]
    return host


# ---------------------------------------------------------------------------
# In-memory tracking state.
#
# Deliberately not persisted: it's the output of a live event stream
# (what have we heard, and when), not configuration. A restart just
# means every device reads offline until mDNS says otherwise again,
# same as last_seen_at going stale used to mean under the old design.
# All mutation happens from the asyncio event loop (callbacks and the
# sweep task's to_thread body run without overlapping each other on
# the GIL in practice, and nothing here does blocking I/O while holding
# a reference into this dict), so no separate lock is used.
# ---------------------------------------------------------------------------


@dataclass
class _DeviceState:
    online: bool = False
    consecutive_misses: int = 0


_state: dict[str, _DeviceState] = {}


def is_online(device_id: str) -> bool:
    state = _state.get(device_id)
    return state.online if state else False


def _reset_state() -> None:
    """Test-only: clear tracking state between tests."""
    _state.clear()


# ---------------------------------------------------------------------------
# Matching a resolved mDNS record back to a Device row
# ---------------------------------------------------------------------------


def match_device_by_hostname(mdns_name: str, devices: list[Device]) -> Device | None:
    for d in devices:
        if d.mdns_name == mdns_name:
            return d
    return None


def match_device_by_ip(ip: str, devices: list[Device]) -> Device | None:
    """Only for devices with no mdns_name yet -- added by IP before mDNS
    ever saw them, or added before this feature existed. Once matched,
    mdns_name gets backfilled (see mark_online) so future matches (and
    DHCP-reassignment handling) go through the hostname, not the IP."""
    for d in devices:
        if d.mdns_name is None and strip_port(d.host) == ip:
            return d
    return None


# ---------------------------------------------------------------------------
# State transitions. Each takes an already-open db session and leaves the
# caller responsible for commit(), so callers can batch multiple devices
# (the sweep) or a single one (an event handler) into one transaction.
# ---------------------------------------------------------------------------


def mark_online(db, device: Device, *, ip: str | None = None, mdns_name: str | None = None) -> None:
    state = _state.setdefault(device.id, _DeviceState())
    state.online = True
    state.consecutive_misses = 0
    device.last_seen_at = utcnow()

    if mdns_name and device.mdns_name != mdns_name:
        device.mdns_name = mdns_name

    if ip:
        stored_ip = strip_port(device.host)
        if stored_ip != ip:
            suffix = device.host[len(stored_ip):]  # "" or ":NNNN", port survives an IP change
            logger.info(
                "Device %s (%r) mDNS-resolved IP changed %s -> %s (DHCP reassignment)",
                device.id, device.name, stored_ip, ip,
            )
            device.host = f"{ip}{suffix}"

    db.add(device)


def mark_offline_immediate(db, device: Device) -> None:
    """Goodbye packet path: bypasses the miss-counter debounce entirely."""
    state = _state.setdefault(device.id, _DeviceState())
    state.online = False
    state.consecutive_misses = 0


# ---------------------------------------------------------------------------
# Sweep: the one timer-driven piece, for silent (no-goodbye) disappearance.
# ---------------------------------------------------------------------------


def is_hostname_live(zc: Zeroconf, mdns_name: str, now_ms: float) -> bool:
    """True if zeroconf's cache still holds a non-expired A record for
    this hostname. Pure cache lookup -- no network I/O -- since the
    browser and goodbye listener are what keep the cache populated."""
    records = zc.cache.get_all_by_details(to_fqdn(mdns_name), zc_const._TYPE_A, zc_const._CLASS_IN)
    return any(not r.is_expired(now_ms) for r in records)


def sweep_tick(zc: Zeroconf) -> None:
    """One pass: for every device with a known mdns_name, check whether
    its A record is still live. Devices with no mdns_name yet (never
    matched by mDNS) are skipped here -- there's nothing to check --
    and stay offline until an Added/Updated event backfills one."""
    now_ms = current_time_millis()
    with SessionLocal() as db:
        devices = db.execute(select(Device).where(Device.mdns_name.isnot(None))).scalars().all()
        for device in devices:
            live = is_hostname_live(zc, device.mdns_name, now_ms)
            state = _state.setdefault(device.id, _DeviceState())
            if live:
                if state.consecutive_misses or not state.online:
                    state.consecutive_misses = 0
                    state.online = True
                    device.last_seen_at = utcnow()
                    db.add(device)
            else:
                state.consecutive_misses += 1
                if state.online and state.consecutive_misses >= OFFLINE_MISS_THRESHOLD:
                    state.online = False
                    logger.info(
                        "Device %s (%r) missed %d consecutive mDNS refresh cycles; marking offline",
                        device.id, device.name, state.consecutive_misses,
                    )
        db.commit()


async def _sweep_forever(zc: Zeroconf) -> None:
    while True:
        try:
            await asyncio.to_thread(sweep_tick, zc)
        except Exception:
            logger.exception("mDNS sweep failed; will retry next interval")
        await asyncio.sleep(SWEEP_INTERVAL_SECONDS)


# ---------------------------------------------------------------------------
# Fast paths: resolved service (Added/Updated) and goodbye (A record TTL=0)
# ---------------------------------------------------------------------------


def _apply_resolved_service(mdns_name: str, ip: str | None) -> None:
    with SessionLocal() as db:
        devices = db.execute(select(Device)).scalars().all()
        device = match_device_by_hostname(mdns_name, devices)
        if device is None and ip:
            device = match_device_by_ip(ip, devices)
        if device is None:
            return
        mark_online(db, device, ip=ip, mdns_name=mdns_name)
        db.commit()


async def _resolve_and_mark_online(zc: Zeroconf, name: str) -> None:
    info = AsyncServiceInfo(SERVICE_TYPE, name)
    try:
        ok = await info.async_request(zc, RESOLVE_TIMEOUT_MS)
    except Exception:
        logger.exception("Failed to resolve mDNS service %r", name)
        return
    if not ok or not info.server:
        return
    mdns_name = strip_local_suffix(info.server)
    addresses = info.parsed_addresses()
    ip = addresses[0] if addresses else None
    await asyncio.to_thread(_apply_resolved_service, mdns_name, ip)


def _make_browser_handler(zc: Zeroconf):
    def handler(zeroconf, service_type, name, state_change):
        if state_change in (ServiceStateChange.Added, ServiceStateChange.Updated):
            asyncio.create_task(_resolve_and_mark_online(zc, name))
        # ServiceStateChange.Removed is intentionally not handled -- see
        # the module docstring for why.
    return handler


def _apply_goodbye(mdns_name: str) -> None:
    with SessionLocal() as db:
        stmt = select(Device).where(Device.mdns_name == mdns_name)
        device = db.execute(stmt).scalar_one_or_none()
        if device is None:
            return
        mark_offline_immediate(db, device)
        db.commit()
    logger.info("Device %r sent an mDNS goodbye packet; marking offline immediately", mdns_name)


class _GoodbyeListener(RecordUpdateListener):
    """Watches every A record on the wire for TTL=0 -- an mDNS goodbye
    announcement, sent on clean shutdown. Cheap: a name compare against
    whatever's currently tracked, no network I/O of its own."""

    def async_update_records(self, zc: Zeroconf, now: float, records) -> None:
        for record_update in records:
            record = record_update.new
            if record.type != zc_const._TYPE_A or record.ttl != 0:
                continue
            asyncio.create_task(asyncio.to_thread(_apply_goodbye, strip_local_suffix(record.name)))


# ---------------------------------------------------------------------------
# Lifecycle: the persistent listener, started once from app.main
# ---------------------------------------------------------------------------


@dataclass
class MdnsMonitor:
    azc: AsyncZeroconf
    browser: AsyncServiceBrowser
    goodbye_listener: _GoodbyeListener
    sweep_task: asyncio.Task = field(repr=False)


async def start() -> MdnsMonitor | None:
    """Starts the persistent listener. Returns None (and logs a warning
    instead of crashing app startup) if it can't be started -- most
    likely because UDP multicast isn't reachable, e.g. Docker's default
    bridge network, which is exactly why network_mode: host is now a
    hard requirement (see README/docker-compose.yml)."""
    if not config.MDNS_ENABLED:
        logger.info("mDNS listener disabled (MDNS_ENABLED=false)")
        return None

    try:
        azc = AsyncZeroconf()
        goodbye_listener = _GoodbyeListener()
        azc.zeroconf.async_add_listener(goodbye_listener, None)
        browser = AsyncServiceBrowser(
            azc.zeroconf, SERVICE_TYPE, handlers=[_make_browser_handler(azc.zeroconf)]
        )
    except Exception:
        logger.exception(
            "Could not start the mDNS listener; device online/offline status will not "
            "update. This almost always means UDP multicast (224.0.0.251:5353) isn't "
            "reachable from this container -- see the network_mode: host requirement "
            "documented in docker-compose.yml."
        )
        return None

    sweep_task = asyncio.create_task(_sweep_forever(azc.zeroconf))
    return MdnsMonitor(
        azc=azc, browser=browser, goodbye_listener=goodbye_listener, sweep_task=sweep_task
    )


async def stop(monitor: MdnsMonitor | None) -> None:
    if monitor is None:
        return
    monitor.sweep_task.cancel()
    try:
        await monitor.sweep_task
    except asyncio.CancelledError:
        pass
    await monitor.browser.async_cancel()
    monitor.azc.zeroconf.async_remove_listener(monitor.goodbye_listener)
    await monitor.azc.async_close()


# ---------------------------------------------------------------------------
# Discovery: one-shot, bounded browse for the add-device flow
# ---------------------------------------------------------------------------


async def _resolve_for_scan(zc: Zeroconf, name: str, found: dict[str, dict]) -> None:
    info = AsyncServiceInfo(SERVICE_TYPE, name)
    try:
        ok = await info.async_request(zc, RESOLVE_TIMEOUT_MS)
    except Exception:
        logger.exception("Failed to resolve mDNS service %r during scan", name)
        return
    if not ok or not info.server:
        return
    addresses = info.parsed_addresses()
    if not addresses:
        return
    mdns_name = strip_local_suffix(info.server)
    found[mdns_name] = {
        "mdns_name": mdns_name,
        "host": addresses[0],
        "name": info.get_name(),
        "port": info.port,
    }


async def scan(timeout: float = 5.0) -> list[dict]:
    """One-shot, bounded browse for the add-device flow. Independent of
    the persistent monitor above -- its own short-lived AsyncZeroconf,
    closed when the scan ends -- so a scan works (or fails) on its own,
    regardless of whether the persistent listener managed to start."""
    azc = AsyncZeroconf()
    found: dict[str, dict] = {}

    def handler(zeroconf, service_type, name, state_change):
        if state_change is ServiceStateChange.Added:
            asyncio.create_task(_resolve_for_scan(zeroconf, name, found))

    browser = AsyncServiceBrowser(azc.zeroconf, SERVICE_TYPE, handlers=[handler])
    try:
        await asyncio.sleep(timeout)
    finally:
        await browser.async_cancel()
        await azc.async_close()
    return list(found.values())
