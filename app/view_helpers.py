from datetime import datetime, timedelta, timezone

from sqlalchemy import func, select
from sqlalchemy.orm import Session, selectinload

from app.models import Device, Schedule, ScheduleExecution
from app.schemas import DeviceRead, ScheduleRead


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
        .options(selectinload(Schedule.device), selectinload(Schedule.action))
        .order_by(func.lower(Schedule.name))
    )
    if device_id:
        stmt = stmt.where(Schedule.device_id == device_id)

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
        .options(
            selectinload(ScheduleExecution.schedule).selectinload(Schedule.action),
            selectinload(ScheduleExecution.device),
        )
        .order_by(ScheduleExecution.fired_at.desc())
    )
    if device_id:
        stmt = stmt.where(ScheduleExecution.device_id == device_id)
    if since != "all":
        cutoff = now_utc - timedelta(days=int(since))
        stmt = stmt.where(ScheduleExecution.fired_at >= cutoff.replace(tzinfo=None))
    stmt = stmt.offset(offset).limit(limit + 1)
    rows = list(db.execute(stmt).scalars())
    return rows


