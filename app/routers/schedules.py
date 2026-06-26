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
from sqlalchemy import select
from sqlalchemy.orm import Session

from app import wled_client
from app.database import get_db
from app.models import (
    Action,
    Device,
    ExecutionStatus,
    Schedule,
    ScheduleExecution,
    Settings,
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
from app.wled_client import WledClientError

router = APIRouter(prefix="/api/schedules", tags=["schedules"])

_TRIGGER_FIELDS = {
    "trigger_type",
    "time_of_day",
    "offset_minutes",
    "days_of_week",
    "start_date",
    "end_date",
}


def _get_schedule_or_404(db: Session, schedule_id: str) -> Schedule:
    schedule = db.get(Schedule, schedule_id)
    if schedule is None:
        raise HTTPException(status_code=404, detail="Schedule not found")
    return schedule


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
            settings=settings,
            now_utc=utcnow(),
        )
    except (LocationNotConfigured, ValueError) as exc:
        db.rollback()
        raise HTTPException(status_code=422, detail=str(exc)) from exc


@router.post("", response_model=ScheduleRead, status_code=201)
def create_schedule(payload: ScheduleCreate, db: Session = Depends(get_db)) -> Schedule:
    if db.get(Device, payload.device_id) is None:
        raise HTTPException(status_code=404, detail="Device not found")
    if db.get(Action, payload.action_id) is None:
        raise HTTPException(status_code=404, detail="Action not found")

    schedule = Schedule(
        name=payload.name,
        device_id=payload.device_id,
        action_id=payload.action_id,
        trigger_type=payload.trigger_type,
        time_of_day=payload.time_of_day,
        offset_minutes=payload.offset_minutes,
        days_of_week=payload.days_of_week,
        start_date=payload.start_date,
        end_date=payload.end_date,
        enabled=payload.enabled,
    )
    _recompute_next_run_at(db, schedule)  # may raise 422 before anything is added
    db.add(schedule)
    db.commit()
    db.refresh(schedule)
    return schedule


@router.get("", response_model=list[ScheduleRead])
def list_schedules(device_id: str | None = None, db: Session = Depends(get_db)) -> list[Schedule]:
    stmt = select(Schedule).order_by(Schedule.name)
    if device_id is not None:
        stmt = stmt.where(Schedule.device_id == device_id)
    return list(db.execute(stmt).scalars())


@router.get("/{schedule_id}", response_model=ScheduleRead)
def get_schedule(schedule_id: str, db: Session = Depends(get_db)) -> Schedule:
    return _get_schedule_or_404(db, schedule_id)


@router.patch("/{schedule_id}", response_model=ScheduleRead)
def update_schedule(
    schedule_id: str, payload: ScheduleUpdate, db: Session = Depends(get_db)
) -> Schedule:
    schedule = _get_schedule_or_404(db, schedule_id)

    if payload.device_id is not None and db.get(Device, payload.device_id) is None:
        raise HTTPException(status_code=404, detail="Device not found")
    if payload.action_id is not None and db.get(Action, payload.action_id) is None:
        raise HTTPException(status_code=404, detail="Action not found")

    update_fields = payload.model_dump(exclude_unset=True)

    try:
        validated = merge_and_validate_schedule(schedule, payload)
    except ValidationError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc

    schedule.name = validated.name
    schedule.device_id = validated.device_id
    schedule.action_id = validated.action_id
    schedule.trigger_type = validated.trigger_type
    schedule.time_of_day = validated.time_of_day
    schedule.offset_minutes = validated.offset_minutes
    schedule.days_of_week = validated.days_of_week
    schedule.start_date = validated.start_date
    schedule.end_date = validated.end_date
    schedule.enabled = validated.enabled

    if _TRIGGER_FIELDS & update_fields.keys():
        _recompute_next_run_at(db, schedule)  # may raise 422

    db.commit()
    db.refresh(schedule)
    return schedule


@router.delete("/{schedule_id}", status_code=204)
def delete_schedule(schedule_id: str, db: Session = Depends(get_db)) -> None:
    schedule = _get_schedule_or_404(db, schedule_id)
    db.delete(schedule)
    db.commit()


@router.post("/{schedule_id}/run-now", response_model=ScheduleExecutionRead)
def run_now(schedule_id: str, db: Session = Depends(get_db)) -> ScheduleExecution:
    schedule = _get_schedule_or_404(db, schedule_id)
    action = schedule.action
    device = schedule.device

    execution = ScheduleExecution(
        schedule_id=schedule.id,
        device_id=device.id,
        status=ExecutionStatus.FAILED,
        request_payload=action.payload,
    )

    try:
        wled_client.post_state(device.host, action.payload, transition_ms=action.transition_ms)
    except WledClientError as exc:
        execution.error_message = str(exc)
    else:
        execution.status = ExecutionStatus.SUCCESS
        schedule.last_run_at = utcnow()

    db.add(execution)
    db.commit()
    db.refresh(execution)
    return execution


@router.get("/{schedule_id}/executions", response_model=list[ScheduleExecutionRead])
def list_executions(
    schedule_id: str, limit: int = 20, offset: int = 0, db: Session = Depends(get_db)
) -> list[ScheduleExecution]:
    _get_schedule_or_404(db, schedule_id)
    limit = max(1, min(limit, 100))
    stmt = (
        select(ScheduleExecution)
        .where(ScheduleExecution.schedule_id == schedule_id)
        .order_by(ScheduleExecution.fired_at.desc())
        .limit(limit)
        .offset(offset)
    )
    return list(db.execute(stmt).scalars())
