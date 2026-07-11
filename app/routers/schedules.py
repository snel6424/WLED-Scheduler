"""Schedule endpoints.

Two pieces of real logic live here rather than in app.schemas:

- next_run_at is computed on create, and recomputed on update only
  when a trigger-related field actually changed (trigger_type,
  time_of_day, offset_minutes, days_of_week). Renaming a schedule or
  toggling `enabled` shouldn't trigger a sunrise/sunset recalculation.
- run-now fires regardless of `enabled`, since it's the only
  verification path an Action has, given there is no preview button
  by design.
"""

from fastapi import APIRouter, Depends, HTTPException
from pydantic import ValidationError
from sqlalchemy import select, update
from sqlalchemy.orm import Session

from app import wled_client
from app.database import get_db
from app.models import (
    Action,
    ActionType,
    Device,
    ExecutionStatus,
    Schedule,
    ScheduleExecution,
    Settings,
    schedule_devices,
    utcnow,
)
from app.scheduling import compute_next_run_at
from app.schemas import (
    ScheduleCreate,
    ScheduleExecutionRead,
    ScheduleRead,
    ScheduleUpdate,
)
from app.sun import LocationNotConfigured
from app.validation import merge_and_validate_schedule
from app.view_helpers import (
    build_device_results,
    effective_device_preset,
    load_devices_by_id,
    load_schedule_device_presets,
    schedule_to_read_dict,
)
from app.wled_client import WledClientError

router = APIRouter(prefix="/api/schedules", tags=["schedules"])

_TRIGGER_FIELDS = {
    "trigger_type",
    "time_of_day",
    "offset_minutes",
    "days_of_week",
    "start_date",
    "end_date",
    "repeat_annually",
}


def _get_schedule_or_404(db: Session, schedule_id: str) -> Schedule:
    schedule = db.get(Schedule, schedule_id)
    if schedule is None:
        raise HTTPException(status_code=404, detail="Schedule not found")
    return schedule


def _get_devices_or_404(db: Session, device_ids: list[str]) -> list[Device]:
    devices = list(db.execute(select(Device).where(Device.id.in_(device_ids))).scalars())
    found_ids = {d.id for d in devices}
    missing = [d for d in device_ids if d not in found_ids]
    if missing:
        raise HTTPException(status_code=404, detail=f"Device not found: {missing[0]}")
    # Preserve the caller's order/de-duplication rather than whatever
    # order the IN (...) query happened to return.
    by_id = {d.id: d for d in devices}
    seen: dict[str, Device] = {}
    for device_id in device_ids:
        seen[device_id] = by_id[device_id]
    return list(seen.values())


def _resolve_device_presets(
    action_type: ActionType,
    device_ids: list[str],
    device_presets: dict[str, int] | None,
    action_payload: dict,
) -> dict[str, int | None]:
    """What to persist into schedule_devices.preset for each linked
    device. A state action never gets a preset override (every entry is
    None: it applies the same Action payload to every device uniformly).
    A preset action targeting a single device may rely on the Action's
    own shared `ps` (the existing single-dropdown form doesn't need to
    send an explicit mapping at all); targeting more than one device
    requires an explicit mapping covering every linked device, since
    there's no single shared preset left to fall back to once the form
    shows a dropdown per device."""
    if action_type != ActionType.PRESET:
        return dict.fromkeys(device_ids)

    device_presets = device_presets or {}
    if len(device_ids) == 1:
        device_id = device_ids[0]
        return {device_id: device_presets.get(device_id, action_payload.get("ps"))}

    missing = [d for d in device_ids if d not in device_presets]
    if missing:
        raise HTTPException(
            status_code=422,
            detail=f"device_presets is missing an entry for device(s): {', '.join(missing)}",
        )
    return {d: device_presets[d] for d in device_ids}


def _write_device_presets(db: Session, schedule_id: str, presets: dict[str, int | None]) -> None:
    for device_id, preset in presets.items():
        db.execute(
            update(schedule_devices)
            .where(
                schedule_devices.c.schedule_id == schedule_id,
                schedule_devices.c.device_id == device_id,
            )
            .values(preset=preset)
        )


def _schedule_response(db: Session, schedule: Schedule) -> ScheduleRead:
    presets = load_schedule_device_presets(db, [schedule.id]).get(schedule.id, {})
    return ScheduleRead.model_validate(schedule_to_read_dict(schedule, presets))


def _execution_response(db: Session, execution: ScheduleExecution) -> dict:
    devices_by_id = load_devices_by_id(db, {r["device_id"] for r in execution.device_results})
    return {
        "id": execution.id,
        "schedule_id": execution.schedule_id,
        "fired_at": execution.fired_at,
        "device_results": build_device_results(devices_by_id, execution.device_results),
        "request_payload": execution.request_payload,
    }


def _recompute_next_run_at(db: Session, schedule: Schedule) -> None:
    settings = db.get(Settings, 1)
    try:
        schedule.next_run_at = compute_next_run_at(
            trigger_type=schedule.trigger_type,
            time_of_day=schedule.time_of_day,
            offset_minutes=schedule.offset_minutes,
            days_of_week=schedule.days_of_week,
            start_date=schedule.start_date,
            end_date=schedule.end_date,
            repeat_annually=schedule.repeat_annually,
            settings=settings,
            now_utc=utcnow(),
        )
    except (LocationNotConfigured, ValueError) as exc:
        db.rollback()
        raise HTTPException(status_code=422, detail=str(exc)) from exc


@router.post("", response_model=ScheduleRead, status_code=201)
def create_schedule(payload: ScheduleCreate, db: Session = Depends(get_db)) -> ScheduleRead:
    devices = _get_devices_or_404(db, payload.device_ids)
    action = db.get(Action, payload.action_id)
    if action is None:
        raise HTTPException(status_code=404, detail="Action not found")

    device_presets = _resolve_device_presets(
        action.type, payload.device_ids, payload.device_presets, action.payload
    )

    schedule = Schedule(
        name=payload.name,
        description=payload.description,
        devices=devices,
        action_id=payload.action_id,
        trigger_type=payload.trigger_type,
        time_of_day=payload.time_of_day,
        offset_minutes=payload.offset_minutes,
        days_of_week=payload.days_of_week,
        start_date=payload.start_date,
        end_date=payload.end_date,
        repeat_annually=payload.repeat_annually,
        enabled=payload.enabled,
        icon=payload.icon,
    )
    _recompute_next_run_at(db, schedule)  # may raise 422 before anything is added
    db.add(schedule)
    db.flush()  # schedule_devices rows must exist before we can UPDATE them
    _write_device_presets(db, schedule.id, device_presets)
    db.commit()
    db.refresh(schedule)
    return _schedule_response(db, schedule)


@router.get("", response_model=list[ScheduleRead])
def list_schedules(
    device_id: str | None = None, db: Session = Depends(get_db)
) -> list[ScheduleRead]:
    stmt = select(Schedule).order_by(Schedule.name)
    if device_id is not None:
        stmt = stmt.where(Schedule.devices.any(Device.id == device_id))
    schedules = list(db.execute(stmt).scalars())
    presets_by_schedule = load_schedule_device_presets(db, [s.id for s in schedules])
    return [
        ScheduleRead.model_validate(schedule_to_read_dict(s, presets_by_schedule.get(s.id, {})))
        for s in schedules
    ]


@router.get("/{schedule_id}", response_model=ScheduleRead)
def get_schedule(schedule_id: str, db: Session = Depends(get_db)) -> ScheduleRead:
    schedule = _get_schedule_or_404(db, schedule_id)
    return _schedule_response(db, schedule)


@router.patch("/{schedule_id}", response_model=ScheduleRead)
def update_schedule(
    schedule_id: str, payload: ScheduleUpdate, db: Session = Depends(get_db)
) -> ScheduleRead:
    schedule = _get_schedule_or_404(db, schedule_id)

    new_devices = None
    if payload.device_ids is not None:
        new_devices = _get_devices_or_404(db, payload.device_ids)
    final_action = db.get(Action, payload.action_id) if payload.action_id is not None else schedule.action
    if final_action is None:
        raise HTTPException(status_code=404, detail="Action not found")

    update_fields = payload.model_dump(exclude_unset=True)

    try:
        validated = merge_and_validate_schedule(schedule, payload)
    except ValidationError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc

    schedule.name = validated.name
    if new_devices is not None:
        schedule.devices = new_devices
    schedule.action_id = validated.action_id
    schedule.trigger_type = validated.trigger_type
    schedule.time_of_day = validated.time_of_day
    schedule.offset_minutes = validated.offset_minutes
    schedule.days_of_week = validated.days_of_week
    schedule.start_date = validated.start_date
    schedule.end_date = validated.end_date
    schedule.repeat_annually = validated.repeat_annually
    schedule.enabled = validated.enabled
    if "icon" in update_fields:
        schedule.icon = update_fields["icon"]
    if "description" in update_fields:
        schedule.description = update_fields["description"]

    if _TRIGGER_FIELDS & update_fields.keys():
        _recompute_next_run_at(db, schedule)  # may raise 422

    db.flush()  # schedule_devices rows must reflect any device reassignment above
    final_device_ids = [d.id for d in schedule.devices]
    device_presets = _resolve_device_presets(
        final_action.type, final_device_ids, payload.device_presets, final_action.payload
    )
    _write_device_presets(db, schedule.id, device_presets)

    db.commit()
    db.refresh(schedule)
    return _schedule_response(db, schedule)


@router.delete("/{schedule_id}", status_code=204)
def delete_schedule(schedule_id: str, db: Session = Depends(get_db)) -> None:
    schedule = _get_schedule_or_404(db, schedule_id)
    db.delete(schedule)
    db.commit()


@router.post("/{schedule_id}/run-now", response_model=ScheduleExecutionRead)
def run_now(schedule_id: str, db: Session = Depends(get_db)) -> dict:
    schedule = _get_schedule_or_404(db, schedule_id)
    action = schedule.action

    payload = action.payload
    if action.type == ActionType.STATE and payload.get("on") is not False and payload.get("seg"):
        segs = payload["seg"]
        payload = {**payload, "seg": [{**segs[0], "fx": 0}, *segs[1:]]}

    device_presets = load_schedule_device_presets(db, [schedule.id]).get(schedule.id, {})

    device_results = []
    any_success = False
    for device in schedule.devices:
        device_payload = payload
        if action.type == ActionType.PRESET:
            device_payload = {**payload, "ps": effective_device_preset(action, device.id, device_presets)}
        try:
            wled_client.post_state(device.host, device_payload, transition_ms=action.transition_ms)
        except WledClientError as exc:
            device_results.append(
                {
                    "device_id": device.id,
                    "status": ExecutionStatus.FAILED.value,
                    "error_message": str(exc),
                }
            )
        else:
            any_success = True
            device_results.append(
                {
                    "device_id": device.id,
                    "status": ExecutionStatus.SUCCESS.value,
                    "error_message": None,
                }
            )

    if any_success:
        schedule.last_run_at = utcnow()

    execution = ScheduleExecution(
        schedule_id=schedule.id,
        device_results=device_results,
        request_payload=action.payload,
    )
    db.add(execution)
    db.commit()
    db.refresh(execution)
    return _execution_response(db, execution)


@router.get("/{schedule_id}/executions", response_model=list[ScheduleExecutionRead])
def list_executions(
    schedule_id: str, limit: int = 20, offset: int = 0, db: Session = Depends(get_db)
) -> list[dict]:
    _get_schedule_or_404(db, schedule_id)
    limit = max(1, min(limit, 100))
    stmt = (
        select(ScheduleExecution)
        .where(ScheduleExecution.schedule_id == schedule_id)
        .order_by(ScheduleExecution.fired_at.desc())
        .limit(limit)
        .offset(offset)
    )
    executions = list(db.execute(stmt).scalars())
    devices_by_id = load_devices_by_id(
        db, {r["device_id"] for e in executions for r in e.device_results}
    )
    return [
        {
            "id": e.id,
            "schedule_id": e.schedule_id,
            "fired_at": e.fired_at,
            "device_results": build_device_results(devices_by_id, e.device_results),
            "request_payload": e.request_payload,
        }
        for e in executions
    ]
