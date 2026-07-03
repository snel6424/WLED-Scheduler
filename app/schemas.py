"""Pydantic schemas for the API contract.

Reuses the enums from app.models directly (ActionType, TriggerType,
ExecutionStatus) rather than redefining them, so there is exactly one
source of truth between the ORM layer and the API layer.

Payload validation for Action is deliberately strict (extra="forbid")
rather than permissive. This isn't just defensive coding, it's how
the agreed v1 scope (on/off, brightness, color, one effect and
palette; no sx/ix, no playlists) gets enforced at the API boundary
instead of just living in a planning doc.
"""

from datetime import date, datetime, time
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, ValidationError, computed_field, model_validator

from app.models import ActionType, ExecutionStatus, TriggerType, compute_overall_status

# ---------------------------------------------------------------------------
# Action payload sub-schemas
# ---------------------------------------------------------------------------


class PresetPayload(BaseModel):
    ps: int = Field(..., ge=0, description="WLED preset id")
    n: str | None = Field(None, description="Preset name at the time the action was saved")

    model_config = ConfigDict(extra="forbid")


class SegmentPayload(BaseModel):
    col: list[list[int]] | None = Field(
        None, description="[[r, g, b], ...] primary/secondary/tertiary"
    )
    fx: int | None = Field(None, ge=0, description="Effect index")
    pal: int | None = Field(None, ge=0, description="Palette index")

    model_config = ConfigDict(extra="forbid")


class StatePayload(BaseModel):
    on: bool | None = None
    bri: int | None = Field(None, ge=0, le=255)
    seg: list[SegmentPayload] | None = None

    model_config = ConfigDict(extra="forbid")


def _validate_payload_shape(action_type: ActionType, payload: dict) -> dict:
    """Shared between ActionCreate and ActionUpdate. Returns the
    normalized payload (nulls stripped) so what hits the database is
    always clean, not whatever shape the client happened to send."""
    schema = PresetPayload if action_type == ActionType.PRESET else StatePayload
    try:
        validated = schema.model_validate(payload)
    except ValidationError as exc:
        raise ValueError(f"payload does not match type={action_type.value}: {exc}") from exc
    return validated.model_dump(exclude_none=True)


# ---------------------------------------------------------------------------
# Action
# ---------------------------------------------------------------------------


class ActionCreate(BaseModel):
    name: str = Field(..., min_length=1, max_length=100)
    type: ActionType
    payload: dict
    transition_ms: int | None = Field(None, ge=0)

    @model_validator(mode="after")
    def validate_payload(self) -> "ActionCreate":
        self.payload = _validate_payload_shape(self.type, self.payload)
        return self


class ActionUpdate(BaseModel):
    name: str | None = Field(None, min_length=1, max_length=100)
    type: ActionType | None = None
    payload: dict | None = None
    transition_ms: int | None = Field(None, ge=0)
    # No cross-field validator here, deliberately. Whether this update's
    # type/payload combination is actually valid depends on the existing
    # record for any field not included in this particular PATCH body, so
    # that check happens once, centrally, in app.validation.merge_and_validate_action.


class ActionRead(BaseModel):
    id: str
    name: str
    type: ActionType
    payload: dict
    transition_ms: int | None
    created_at: datetime
    updated_at: datetime

    model_config = ConfigDict(from_attributes=True)


# ---------------------------------------------------------------------------
# Device
# ---------------------------------------------------------------------------


class DeviceCreate(BaseModel):
    name: str | None = Field(None, min_length=1, max_length=100)
    host: str = Field(..., min_length=1, max_length=255)
    room: str | None = Field(None, max_length=100)
    # Set when a device is added from the mDNS scan results rather than
    # typed in by hand; lets app.mdns start tracking it immediately
    # instead of waiting to backfill this by matching on IP later.
    mdns_name: str | None = Field(None, max_length=255)


class DeviceUpdate(BaseModel):
    name: str | None = Field(None, min_length=1, max_length=100)
    room: str | None = Field(None, max_length=100)
    icon: str | None = Field(None, max_length=50)


class DeviceRead(BaseModel):
    id: str
    name: str
    host: str
    room: str | None
    mac: str | None
    mdns_name: str | None
    last_seen_at: datetime | None
    capabilities: dict | None
    powered_on: bool | None
    icon: str | None
    created_at: datetime
    updated_at: datetime

    model_config = ConfigDict(from_attributes=True)

    @computed_field
    @property
    def online(self) -> bool:
        """Derived, not stored on this model: reflects whatever
        app.mdns's persistent listener currently believes about this
        device, updated by mDNS callback (an Added/Updated event, a
        goodbye packet, or a debounced sweep miss) rather than computed
        fresh here from a timestamp."""
        from app import mdns

        return mdns.is_online(self.id)


class DeviceSummary(BaseModel):
    """Slim version embedded in ScheduleRead. A schedule list doesn't
    need every device's full capabilities blob along for the ride."""

    id: str
    name: str
    host: str
    icon: str | None

    model_config = ConfigDict(from_attributes=True)


class PresetRead(BaseModel):
    """One entry from a device's live /presets.json, not cached."""

    id: int
    name: str


# ---------------------------------------------------------------------------
# Settings
# ---------------------------------------------------------------------------


class SettingsRead(BaseModel):
    latitude: float | None
    longitude: float | None
    timezone: str | None
    catch_up_missed: bool

    model_config = ConfigDict(from_attributes=True)


class SettingsUpdate(BaseModel):
    latitude: float | None = Field(None, ge=-90, le=90)
    longitude: float | None = Field(None, ge=-180, le=180)
    timezone: str | None = None
    catch_up_missed: bool | None = None
    # Whether clearing latitude/longitude is actually allowed (it isn't,
    # if any sunrise/sunset schedule exists) is router logic, not
    # something this schema can know on its own.


# ---------------------------------------------------------------------------
# Schedule
# ---------------------------------------------------------------------------


class ScheduleBase(BaseModel):
    name: str = Field(..., min_length=1, max_length=100)
    description: str | None = Field(None, max_length=500)
    device_ids: list[str] = Field(..., min_length=1)
    action_id: str
    trigger_type: TriggerType
    time_of_day: time | None = None
    offset_minutes: int | None = Field(None, ge=-720, le=720)
    days_of_week: int = Field(127, ge=0, le=127)
    start_date: date | None = None
    end_date: date | None = None
    repeat_annually: bool = False
    enabled: bool = True
    icon: str | None = Field(None, max_length=50)

    @model_validator(mode="after")
    def validate_trigger_fields(self) -> "ScheduleBase":
        if self.trigger_type == TriggerType.TIME:
            if self.time_of_day is None:
                raise ValueError("time_of_day is required when trigger_type is 'time'")
            if self.offset_minutes is not None:
                raise ValueError("offset_minutes must not be set when trigger_type is 'time'")
        else:
            if self.offset_minutes is None:
                raise ValueError("offset_minutes is required for sunrise/sunset triggers")
            if self.time_of_day is not None:
                raise ValueError("time_of_day must not be set for sunrise/sunset triggers")
        if self.repeat_annually:
            if self.start_date is None or self.end_date is None:
                raise ValueError("start_date and end_date are both required when repeat_annually is true")
        elif self.start_date is not None and self.end_date is not None:
            if self.end_date < self.start_date:
                raise ValueError("end_date must be the same as or after start_date")
        return self


class ScheduleCreate(ScheduleBase):
    pass


class ScheduleUpdate(BaseModel):
    name: str | None = Field(None, min_length=1, max_length=100)
    description: str | None = Field(None, max_length=500)
    device_ids: list[str] | None = Field(None, min_length=1)
    action_id: str | None = None
    trigger_type: TriggerType | None = None
    time_of_day: time | None = None
    offset_minutes: int | None = Field(None, ge=-720, le=720)
    days_of_week: int | None = Field(None, ge=0, le=127)
    enabled: bool | None = None
    start_date: date | None = None
    end_date: date | None = None
    repeat_annually: bool | None = None
    icon: str | None = Field(None, max_length=50)
    # Same reasoning as ActionUpdate: trigger_type/time_of_day/offset_minutes
    # consistency is checked in the router after merging with the existing
    # row, since a partial body doesn't carry enough information alone.


class ScheduleRead(BaseModel):
    id: str
    name: str
    description: str | None
    enabled: bool
    trigger_type: TriggerType
    time_of_day: time | None
    offset_minutes: int | None
    days_of_week: int
    start_date: date | None
    end_date: date | None
    repeat_annually: bool
    next_run_at: datetime | None
    last_run_at: datetime | None
    icon: str | None
    devices: list[DeviceSummary]
    action: ActionRead

    model_config = ConfigDict(from_attributes=True)


OverallStatus = Literal["success", "failed", "partial", "skipped"]


class DeviceResultRead(BaseModel):
    """One device's outcome within a ScheduleExecution. `device` is
    None if that device has since been deleted; device_id inside
    device_results isn't a foreign key (it's embedded in JSON), so it
    can outlive the row it refers to."""

    device: DeviceSummary | None
    status: ExecutionStatus
    error_message: str | None


class ScheduleExecutionRead(BaseModel):
    id: str
    schedule_id: str
    fired_at: datetime
    device_results: list[DeviceResultRead]
    request_payload: dict | None

    model_config = ConfigDict(from_attributes=True)

    @computed_field
    @property
    def overall_status(self) -> OverallStatus:
        return compute_overall_status(
            [{"status": r.status.value} for r in self.device_results]
        )


class ScheduleSummary(BaseModel):
    """Slim, for embedding in the aggregate history view. A history
    entry doesn't need a schedule's full trigger configuration, just
    enough to identify and link to it."""

    id: str
    name: str
    icon: str | None

    model_config = ConfigDict(from_attributes=True)


class ActionSummary(BaseModel):
    """Slim, for embedding in the aggregate history view: just enough
    to describe what the action actually did (turn on, turn off, or
    apply a preset), not the full Action record."""

    type: ActionType
    payload: dict

    model_config = ConfigDict(from_attributes=True)


class HistoryEntryRead(BaseModel):
    """Same underlying ScheduleExecution row as ScheduleExecutionRead,
    but with the schedule and action embedded, since the aggregate
    history view (unlike the per-schedule one) doesn't already have
    that context from the page it's on. device_results carries one
    entry per device the schedule targeted at fire time, same as
    ScheduleExecutionRead."""

    id: str
    fired_at: datetime
    schedule: ScheduleSummary
    action: ActionSummary
    device_results: list[DeviceResultRead]

    model_config = ConfigDict(from_attributes=True)

    @computed_field
    @property
    def overall_status(self) -> OverallStatus:
        return compute_overall_status(
            [{"status": r.status.value} for r in self.device_results]
        )
