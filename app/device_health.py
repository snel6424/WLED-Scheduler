"""Background device reachability check ("ping," in practice an HTTP
request, not ICMP, since that needs raw sockets Python doesn't have
by default). Same loop pattern as scheduler.py: a plain sync tick()
for testability, wrapped in an asyncio task for the real loop.

This intentionally does not use mDNS. Auto-discovery via mDNS is
still explicitly deferred to post-v1; this loop only re-checks
devices that already exist, it doesn't find new ones.

Online/offline itself isn't stored as a column. A device counts as
online if last_seen_at is recent, computed in DeviceRead. This loop's
only job is to keep last_seen_at honest by updating it on every
successful check and leaving it alone on failure, so it naturally
goes stale (and the device reads as offline) without a separate flag
to keep in sync.
"""

import asyncio
import logging

from sqlalchemy import select

from app import config, wled_client
from app.database import SessionLocal
from app.models import Device, utcnow
from app.wled_client import WledClientError

logger = logging.getLogger("app.device_health")

POLL_INTERVAL_SECONDS = config.DEVICE_HEALTH_CHECK_INTERVAL_SECONDS


def tick() -> None:
    """One pass: check every device, update last_seen_at on success."""
    with SessionLocal() as db:
        devices = db.execute(select(Device)).scalars().all()
        for device in devices:
            try:
                wled_client.get_info(device.host)
            except WledClientError as exc:
                logger.debug("Device %s (%r) did not respond: %s", device.id, device.name, exc)
                continue
            device.last_seen_at = utcnow()
        db.commit()


async def run_forever() -> None:
    """The actual background task, started from app.main's lifespan,
    alongside the scheduler loop, not merged into it: schedule firing
    and device reachability are different concerns with different
    natural intervals, and a slow/unreachable device here shouldn't
    have any chance of delaying a schedule that's actually due."""
    while True:
        try:
            await asyncio.to_thread(tick)
        except Exception:
            logger.exception("Device health check failed; will retry next interval")
        await asyncio.sleep(POLL_INTERVAL_SECONDS)
