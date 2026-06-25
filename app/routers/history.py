"""Aggregate history across every schedule. The per-schedule history
(GET /api/schedules/{id}/executions) already existed; this is its
sibling for the standalone History tab, which needs to show
everything, optionally filtered by device or date range, not just
one schedule's run history.
"""

from datetime import datetime

from fastapi import APIRouter, Depends
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.database import get_db
from app.models import ScheduleExecution
from app.schemas import HistoryEntryRead

router = APIRouter(prefix="/api/history", tags=["history"])


@router.get("", response_model=list[HistoryEntryRead])
def list_history(
    device_id: str | None = None,
    since: datetime | None = None,
    until: datetime | None = None,
    limit: int = 50,
    offset: int = 0,
    db: Session = Depends(get_db),
) -> list[dict]:
    limit = max(1, min(limit, 200))
    stmt = select(ScheduleExecution).order_by(ScheduleExecution.fired_at.desc())
    if device_id is not None:
        stmt = stmt.where(ScheduleExecution.device_id == device_id)
    if since is not None:
        stmt = stmt.where(ScheduleExecution.fired_at >= since)
    if until is not None:
        stmt = stmt.where(ScheduleExecution.fired_at <= until)
    stmt = stmt.offset(offset).limit(limit)
    executions = db.execute(stmt).scalars().all()

    # HistoryEntryRead.action has no direct equivalent on
    # ScheduleExecution itself, only reachable via execution.schedule.action,
    # so each row is built as a dict here rather than relying on
    # from_attributes to traverse that path automatically.
    return [
        {
            "id": e.id,
            "fired_at": e.fired_at,
            "status": e.status,
            "error_message": e.error_message,
            "schedule": e.schedule,
            "device": e.device,
            "action": e.schedule.action,
        }
        for e in executions
    ]
