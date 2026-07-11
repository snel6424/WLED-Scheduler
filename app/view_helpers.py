from datetime import UTC, datetime, timedelta

from sqlalchemy import func, select
from sqlalchemy.orm import Session, selectinload

from app.models import Action, ActionType, Device, Schedule, ScheduleExecution, schedule_devices
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


def load_schedule_device_presets(
    db: Session, schedule_ids: list[str]
) -> dict[str, dict[str, int | None]]:
    """schedule_id -> {device_id: preset override}, straight off the
    schedule_devices join table. Only preset-type actions ever have a
    non-None entry here; see effective_device_preset for how a None
    (never set, or a state action) gets resolved."""
    if not schedule_ids:
        return {}
    rows = db.execute(
        select(
            schedule_devices.c.schedule_id,
            schedule_devices.c.device_id,
            schedule_devices.c.preset,
        ).where(schedule_devices.c.schedule_id.in_(schedule_ids))
    ).all()
    result: dict[str, dict[str, int | None]] = {}
    for row in rows:
        result.setdefault(row.schedule_id, {})[row.device_id] = row.preset
    return result


def effective_device_preset(
    action: Action, device_id: str, device_presets: dict[str, int | None]
) -> int | None:
    """The preset id that will actually be sent to `device_id` for this
    (preset-type) action: the schedule_devices override if one was ever
    saved for this pair, otherwise the Action's own shared `ps`. Always
    None for a state action, since those apply the same payload to every
    device uniformly rather than a preset at all."""
    if action.type != ActionType.PRESET:
        return None
    stored = device_presets.get(device_id)
    return stored if stored is not None else action.payload.get("ps")


def schedule_to_read_dict(schedule: Schedule, device_presets: dict[str, int | None]) -> dict:
    """Builds the dict ScheduleRead.model_validate expects, with each
    device's effective preset resolved in (see effective_device_preset).
    Schedule.devices is a plain list[Device] with no per-pair columns of
    its own, so this can't just be `ScheduleRead.model_validate(schedule)`
    directly the way it used to be."""
    return {
        "id": schedule.id,
        "name": schedule.name,
        "description": schedule.description,
        "enabled": schedule.enabled,
        "trigger_type": schedule.trigger_type,
        "time_of_day": schedule.time_of_day,
        "offset_minutes": schedule.offset_minutes,
        "days_of_week": schedule.days_of_week,
        "start_date": schedule.start_date,
        "end_date": schedule.end_date,
        "repeat_annually": schedule.repeat_annually,
        "next_run_at": schedule.next_run_at,
        "last_run_at": schedule.last_run_at,
        "icon": schedule.icon,
        "devices": [
            {
                "id": d.id,
                "name": d.name,
                "host": d.host,
                "icon": d.icon,
                "preset": effective_device_preset(schedule.action, d.id, device_presets),
            }
            for d in schedule.devices
        ],
        "action": schedule.action,
    }


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
    presets_by_schedule = load_schedule_device_presets(db, [s.id for s in rows])
    reads = [
        ScheduleRead.model_validate(
            schedule_to_read_dict(s, presets_by_schedule.get(s.id, {}))
        )
        for s in rows
    ]
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
    now_utc = now_utc or datetime.now(UTC)
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


