"""Settings endpoints. A true singleton: GET always returns id=1
(bootstrapped at app startup), and there is no POST or DELETE.

PATCH carries one real piece of business logic: clearing latitude or
longitude is blocked if any sunrise/sunset schedule currently depends
on them, mirroring the same "don't silently orphan a schedule" rule
already enforced when deleting an Action.
"""

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.database import get_db
from app.models import Schedule, Settings, TriggerType
from app.schemas import SettingsRead, SettingsUpdate

router = APIRouter(prefix="/api/settings", tags=["settings"])

_SUN_TRIGGERS = (TriggerType.SUNRISE, TriggerType.SUNSET)


@router.get("", response_model=SettingsRead)
def get_settings(db: Session = Depends(get_db)) -> Settings:
    settings = db.get(Settings, 1)
    if settings is None:
        # Should not happen; app startup bootstraps this row. Fail
        # loudly rather than silently fabricating a response.
        raise HTTPException(
            status_code=500, detail="Settings row missing; startup bootstrap may not have run"
        )
    return settings


@router.patch("", response_model=SettingsRead)
def update_settings(payload: SettingsUpdate, db: Session = Depends(get_db)) -> Settings:
    settings = db.get(Settings, 1)
    if settings is None:
        raise HTTPException(
            status_code=500, detail="Settings row missing; startup bootstrap may not have run"
        )

    update_fields = payload.model_dump(exclude_unset=True)

    was_configured = settings.latitude is not None and settings.longitude is not None
    resulting_lat = update_fields.get("latitude", settings.latitude)
    resulting_lng = update_fields.get("longitude", settings.longitude)
    would_be_configured = resulting_lat is not None and resulting_lng is not None

    # Only block a transition from "configured" to "not configered" -- not
    # every update made while location merely happens to be incomplete
    # already. Without this distinction, field-by-field initial setup
    # (latitude saved on blur, then longitude saved separately) would
    # trip this guard on its very first save, and so would any unrelated
    # settings change (timezone, catch_up_missed) made before location
    # was ever configured.
    if was_configured and not would_be_configured:
        blocking = list(
            db.execute(
                select(Schedule.name).where(Schedule.trigger_type.in_(_SUN_TRIGGERS))
            ).scalars()
        )
        if blocking:
            raise HTTPException(
                status_code=409,
                detail=(
                    "Cannot clear latitude/longitude while sunrise/sunset "
                    f"schedules depend on them. Affected: {', '.join(blocking)}"
                ),
            )

    for field, value in update_fields.items():
        setattr(settings, field, value)

    db.commit()
    db.refresh(settings)
    return settings
