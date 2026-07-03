from datetime import datetime, timedelta, timezone

from sqlalchemy import func, select
from sqlalchemy.orm import Session, selectinload

from app.models import Device, Schedule, ScheduleExecution
from app.schemas import DeviceRead, ScheduleRead


def load_devices_by_id(db: Session, device_ids: set[str]) -> dict[str, Device]:
    """Batch-fetch Device rows referenced from one or more executions'
    device_results. Anything in device_ids that no longer exists (the
    device was deleted after the execution fired) is simply absent
    from the returned dict; callers treat a miss as "deleted device"."""
    if not device_ids:
        return {}
    return {d.id: d for d in db.execute(select(Device).where(Device.id.in_(device_ids))).scalars()}


def build_device_results(devices_by_id: dict[str, Device], raw_results: list[dict]) -> list[dict]:
    """Joins an execution's raw device_results (device_id/status/error_message
    dicts straight out of the JSON column) against a devices_by_id lookup,
    shaping each entry for DeviceResultRead / the history templates."""
    return [
        {
            "device": devices_by_id.get(r["device_id"]),
            "status": r["status"],
            "error_message": r.get("error_message"),
        }
        for r in raw_results
    ]


def device_results_contains(device_id: str):
    """EXISTS subquery: does this row's device_results JSON list contain
    an entry for device_id? Used to filter history/executions by device
    now that device_id lives inside a JSON blob rather than its own
    column. Requires SQLite's JSON1 extension (json_each/json_extract),
    bundled into Python's stdlib sqlite3 on any reasonably modern build."""
    je = func.json_each(ScheduleExecution.device_results).table_valued("value")
    return (
        select(1)
        .select_from(je)
        .where(func.json_extract(je.c.value, "$.device_id") == device_id)
        .exists()
    )


def get_device_reads(db: Session, sort: str = "name") -> list[DeviceRead]:
    """Fetch devices and compute derived online status for page rendering."""
    rows = list(db.execute(select(Device)).scalars())
    reads = [DeviceRead.model_validate(d) for d in rows]
    if sort == "status":
        reads.sort(key=lambda d: (not d.online, d.name.lower()))
    else:
        reads.sort(key=lambda d: d.name.lower())
    return reads


def get_schedule_reads(
    db: Session, status_filter: str = "all", device_id: str | None = None
) -> list[ScheduleRead]:
    """Fetch schedules with their related device/action data loaded eagerly."""
    stmt = (
        select(Schedule)
        .options(selectinload(Schedule.devices), selectinload(Schedule.action))
        .order_by(func.lower(Schedule.name))
    )
    if device_id:
        stmt = stmt.where(Schedule.devices.any(Device.id == device_id))

    rows = list(db.execute(stmt).scalars())
    reads = [ScheduleRead.model_validate(s) for s in rows]
    if status_filter == "active":
        reads = [s for s in reads if s.enabled]
    elif status_filter == "inactive":
        reads = [s for s in reads if not s.enabled]
    elif status_filter == "sun":
        reads = [s for s in reads if s.trigger_type.value in ("sunrise", "sunset")]
    return reads


def get_history_execution_rows(
    db: Session,
    *,
    device_id: str | None = None,
    since: str = "7",
    offset: int = 0,
    limit: int = 20,
    now_utc: datetime | None = None,
) -> list[ScheduleExecution]:
    """Fetch history rows with related schedule/device/action data loaded eagerly."""
    now_utc = now_utc or datetime.now(timezone.utc)
    stmt = (
        select(ScheduleExecution)
        .options(selectinload(ScheduleExecution.schedule).selectinload(Schedule.action))
        .order_by(ScheduleExecution.fired_at.desc())
    )
    if device_id:
        stmt = stmt.where(device_results_contains(device_id))
    if since != "all":
        cutoff = now_utc - timedelta(days=int(since))
        stmt = stmt.where(ScheduleExecution.fired_at >= cutoff.replace(tzinfo=None))
    stmt = stmt.offset(offset).limit(limit + 1)
    rows = list(db.execute(stmt).scalars())
    return rows


