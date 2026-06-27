"""Cross-field validation for partial updates.

PATCH endpoints accept any subset of fields, but the cross-field rules
that matter here, an Action's payload shape matching its type, a
Schedule's time_of_day/offset_minutes matching its trigger_type, can
only be checked against the record's *final* state. A request body
that only changes transition_ms says nothing about whether type and
payload still agree, because it doesn't carry either of them.

Both functions below merge the existing ORM row with the partial
update, then re-validate the merged result through the same strict
Create schema used at creation time. That keeps the cross-field rules
written in exactly one place (the model_validator on ActionCreate /
ScheduleBase) and reused for both POST and PATCH, rather than a second,
looser copy living here.

One consequence worth knowing: switching a Schedule's trigger_type
without also explicitly sending the field that no longer applies as
null (for example, moving from "time" to "sunset" without sending
time_of_day: null) raises a validation error rather than silently
carrying the stale value forward. This is intentional, not a bug, and
it means the schedule form needs to clear the irrelevant input
whenever the trigger type changes.
"""

from app import models
from app.schemas import ActionCreate, ActionUpdate, ScheduleCreate, ScheduleUpdate


def merge_and_validate_action(existing: models.Action, update: ActionUpdate) -> ActionCreate:
    """Returns a validated ActionCreate representing what the row would
    look like after applying `update`. Raises pydantic.ValidationError
    if the resulting combination is invalid. Callers apply the
    validated fields back onto `existing`; this function does not
    touch the database itself."""
    merged = {
        "name": existing.name,
        "type": existing.type,
        "payload": existing.payload,
        "transition_ms": existing.transition_ms,
    }
    merged.update(update.model_dump(exclude_unset=True))
    return ActionCreate.model_validate(merged)


def merge_and_validate_schedule(
    existing: models.Schedule, update: ScheduleUpdate
) -> ScheduleCreate:
    """Same idea as merge_and_validate_action, for Schedule. Re-runs the
    trigger_type / time_of_day / offset_minutes consistency check
    against the merged result, not just whatever fields this particular
    PATCH happened to include."""
    merged = {
        "name": existing.name,
        "device_id": existing.device_id,
        "action_id": existing.action_id,
        "trigger_type": existing.trigger_type,
        "time_of_day": existing.time_of_day,
        "offset_minutes": existing.offset_minutes,
        "days_of_week": existing.days_of_week,
        "start_date": existing.start_date,
        "end_date": existing.end_date,
        "repeat_annually": existing.repeat_annually,
        "enabled": existing.enabled,
    }
    merged.update(update.model_dump(exclude_unset=True))
    return ScheduleCreate.model_validate(merged)
