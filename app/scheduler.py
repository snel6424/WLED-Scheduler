"""The background scheduler loop.

Runs as an asyncio task started from FastAPI's lifespan, not a
separate process or worker, per the original architecture decision:
one container, one process, no task queue needed at this scale.

tick() is the actual unit of work: find due schedules, fire or skip
them, recompute next_run_at. It's a plain synchronous function on
purpose, so it's trivially testable without touching asyncio, and
run_forever() wraps it with asyncio.to_thread so a slow tick (a device
that's timing out) can't block the event loop FastAPI's own request
handlers run on.

Catch-up behavior: a schedule overdue by more than a few poll
intervals is treated as "missed", not "normally due". A schedule
that's only a few seconds overdue, just normal polling granularity,
always fires regardless of the catch_up_missed setting; that setting
only decides what happens to a schedule that was actually missed
because the backend itself was down. See Settings.catch_up_missed.
"""

import asyncio
import logging
from datetime import datetime, timedelta

from sqlalchemy import select
from sqlalchemy.orm import Session

from app import config, wled_client
from app.database import SessionLocal
from app.models import ExecutionStatus, Schedule, ScheduleExecution, Settings, utcnow
from app.scheduling import compute_next_run_at
from app.sun import LocationNotConfigured
from app.wled_client import WledClientError

logger = logging.getLogger("app.scheduler")

POLL_INTERVAL_SECONDS = config.SCHEDULER_POLL_INTERVAL_SECONDS

# More than this many poll intervals overdue counts as "missed" rather
# than "normally due". At the default 30s interval that's 90 seconds,
# comfortably more than ordinary polling jitter but nowhere near long
# enough to mistake a real outage for a normal tick.
_STALE_MULTIPLIER = 3


def _is_stale(schedule: Schedule, now: datetime) -> bool:
    threshold = timedelta(seconds=POLL_INTERVAL_SECONDS * _STALE_MULTIPLIER)
    return (now - schedule.next_run_at) > threshold


def _fire(db: Session, schedule: Schedule) -> None:
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
        logger.warning("Schedule %s (%r) failed to fire: %s", schedule.id, schedule.name, exc)
    else:
        execution.status = ExecutionStatus.SUCCESS
        schedule.last_run_at = utcnow()
    db.add(execution)


def _skip(db: Session, schedule: Schedule, now: datetime) -> None:
    overdue_by = now - schedule.next_run_at
    reason = (
        f"Missed by {overdue_by}; catch_up_missed is off, "
        "so it was advanced to its next occurrence without firing."
    )
    logger.info("Schedule %s (%r): %s", schedule.id, schedule.name, reason)
    db.add(
        ScheduleExecution(
            schedule_id=schedule.id,
            device_id=schedule.device_id,
            status=ExecutionStatus.SKIPPED,
            error_message=reason,
        )
    )


def _advance(db: Session, schedule: Schedule, settings: Settings, now: datetime) -> None:
    try:
        schedule.next_run_at = compute_next_run_at(
            trigger_type=schedule.trigger_type,
            time_of_day=schedule.time_of_day,
            offset_minutes=schedule.offset_minutes,
            days_of_week=schedule.days_of_week,
            settings=settings,
            now_utc=now,
        )
    except LocationNotConfigured:
        # Shouldn't happen: PATCH /api/settings blocks clearing location
        # while a sunrise/sunset schedule exists. If it somehow does,
        # don't crash the loop over one bad row, and don't silently
        # disable the user's schedule either. Leave next_run_at as-is;
        # it stays "due" and this gets logged loudly on every tick
        # until a human fixes Settings, which is the right amount of
        # annoying for something that should be unreachable.
        logger.error(
            "Schedule %s (%r) needs sunrise/sunset but location is not "
            "configured; it will keep showing as due until this is fixed.",
            schedule.id,
            schedule.name,
        )


def tick() -> None:
    """One pass over all due, enabled schedules."""
    now = utcnow()
    with SessionLocal() as db:
        settings = db.get(Settings, 1)
        if settings is None:
            logger.error("Settings row missing; skipping this tick entirely")
            return

        due = (
            db.execute(
                select(Schedule)
                .where(Schedule.enabled.is_(True), Schedule.next_run_at <= now)
                .order_by(Schedule.next_run_at)
            )
            .scalars()
            .all()
        )

        for schedule in due:
            if _is_stale(schedule, now) and not settings.catch_up_missed:
                _skip(db, schedule, now)
            else:
                _fire(db, schedule)
            _advance(db, schedule, settings, now)

        db.commit()


async def run_forever() -> None:
    """The actual background task, started from app.main's lifespan."""
    while True:
        try:
            await asyncio.to_thread(tick)
        except Exception:
            # A bad tick should never take down the whole loop; that
            # would silently stop every schedule in the app, forever,
            # until a manual restart. Log it and try again next interval.
            logger.exception("Scheduler tick failed; will retry next interval")
        await asyncio.sleep(POLL_INTERVAL_SECONDS)
