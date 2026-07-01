"""SQLAlchemy models for the WLED scheduler.

Conventions used throughout this file:

- All ids are UUID strings, except Settings, which is a deliberate
  single row table keyed at id=1.
- All datetimes are stored as naive UTC.
- Wall clock concepts (a schedule's time_of_day) are stored as plain
  local time and combined with Settings.timezone at compute time in
  the scheduler. Only the resulting next_run_at is a concrete UTC
  instant. This keeps daylight saving time correct without storing
  anything timezone aware in SQLite.
"""

import enum
import uuid
from datetime import UTC, date, datetime, time

from sqlalchemy import (
    Boolean,
    CheckConstraint,
    Date,
    DateTime,
    Float,
    ForeignKey,
    Index,
    Integer,
    String,
    Text,
    Time,
)
from sqlalchemy import (
    Enum as SAEnum,
)
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, relationship
from sqlalchemy.types import JSON


def generate_uuid() -> str:
    return str(uuid.uuid4())


def utcnow() -> datetime:
    """Naive UTC now. datetime.utcnow() is deprecated as of Python 3.12;
    this keeps the same naive-UTC-everywhere convention without it."""
    return datetime.now(UTC).replace(tzinfo=None)


class Base(DeclarativeBase):
    pass


class TimestampMixin:
    created_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow, nullable=False)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime, default=utcnow, onupdate=utcnow, nullable=False
    )


class ActionType(enum.StrEnum):
    PRESET = "preset"
    STATE = "state"


class TriggerType(enum.StrEnum):
    TIME = "time"
    SUNRISE = "sunrise"
    SUNSET = "sunset"


class ExecutionStatus(enum.StrEnum):
    SUCCESS = "success"
    FAILED = "failed"
    SKIPPED = "skipped"


# Stores the lowercase .value of each enum member rather than SQLAlchemy's
# default of storing the .name. Without this, the CheckConstraints below
# (which compare against "time", "sunrise", etc) would never match.
def _enum_values(enum_cls):
    return SAEnum(enum_cls, values_callable=lambda obj: [e.value for e in obj])


class Device(TimestampMixin, Base):
    __tablename__ = "devices"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=generate_uuid)
    name: Mapped[str] = mapped_column(String(100), nullable=False)
    host: Mapped[str] = mapped_column(String(255), nullable=False, unique=True)
    room: Mapped[str | None] = mapped_column(String(100), nullable=True)
    mac: Mapped[str | None] = mapped_column(String(20), nullable=True)
    last_seen_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    powered_on: Mapped[bool | None] = mapped_column(Boolean, nullable=True)

    # Bonjour hostname, without the trailing ".local". Populated either
    # from the add-device mDNS scan flow or backfilled the first time
    # app.mdns matches an unlabeled device by IP. Devices without this
    # set (e.g. added by IP before mDNS ever saw them) can't be tracked
    # for online/offline until mDNS resolves and backfills it.
    mdns_name: Mapped[str | None] = mapped_column(String(255), nullable=True, unique=True)

    # Cached subset of /json/info: led count, max segments, fx count,
    # palette count, firmware version. Refreshed on add and on manual refresh.
    capabilities: Mapped[dict | None] = mapped_column(JSON, nullable=True)

    # Optional icon key from the icon picker (e.g. "tv", "sofa"). Null means
    # use the generic bulb. Stored as a string key, not raw SVG.
    icon: Mapped[str | None] = mapped_column(String(50), nullable=True)

    schedules: Mapped[list["Schedule"]] = relationship(
        back_populates="device", cascade="all, delete-orphan", passive_deletes=True
    )
    executions: Mapped[list["ScheduleExecution"]] = relationship(
        back_populates="device", passive_deletes=True
    )

    def __repr__(self) -> str:
        return f"Device(id={self.id!r}, name={self.name!r}, host={self.host!r})"


class Settings(Base):
    """Single row table. The app always reads and writes id=1."""

    __tablename__ = "settings"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, default=1)
    latitude: Mapped[float | None] = mapped_column(Float, nullable=True)
    longitude: Mapped[float | None] = mapped_column(Float, nullable=True)
    timezone: Mapped[str | None] = mapped_column(String(64), nullable=True)
    catch_up_missed: Mapped[bool] = mapped_column(default=False, nullable=False)

    __table_args__ = (CheckConstraint("id = 1", name="ck_settings_singleton"),)

    def __repr__(self) -> str:
        return (
            f"Settings(latitude={self.latitude!r}, longitude={self.longitude!r}, "
            f"timezone={self.timezone!r})"
        )


class Action(TimestampMixin, Base):
    __tablename__ = "actions"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=generate_uuid)
    name: Mapped[str] = mapped_column(String(100), nullable=False)
    type: Mapped[ActionType] = mapped_column(_enum_values(ActionType), nullable=False)

    # PRESET: {"ps": <int>}
    # STATE:  a literal WLED state body, e.g. {"on": true, "bri": 180, "seg": [...]}
    payload: Mapped[dict] = mapped_column(JSON, nullable=False)
    transition_ms: Mapped[int | None] = mapped_column(Integer, nullable=True)

    schedules: Mapped[list["Schedule"]] = relationship(back_populates="action")

    __table_args__ = (
        CheckConstraint("type IN ('preset', 'state')", name="ck_action_type_valid"),
    )

    def __repr__(self) -> str:
        return f"Action(id={self.id!r}, name={self.name!r}, type={self.type!r})"


class Schedule(TimestampMixin, Base):
    __tablename__ = "schedules"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=generate_uuid)
    name: Mapped[str] = mapped_column(String(100), nullable=False)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    enabled: Mapped[bool] = mapped_column(default=True, nullable=False)

    device_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("devices.id", ondelete="CASCADE"), nullable=False
    )
    action_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("actions.id", ondelete="RESTRICT"), nullable=False
    )

    trigger_type: Mapped[TriggerType] = mapped_column(_enum_values(TriggerType), nullable=False)

    # Local wall clock time, only set when trigger_type == TIME.
    time_of_day: Mapped[time | None] = mapped_column(Time, nullable=True)

    # Minutes relative to sunrise/sunset, can be negative, only set
    # when trigger_type is SUNRISE or SUNSET.
    offset_minutes: Mapped[int | None] = mapped_column(Integer, nullable=True)

    # Bitmask: bit 0 = Monday ... bit 6 = Sunday. 127 = every day.
    days_of_week: Mapped[int] = mapped_column(Integer, default=127, nullable=False)

    # Optional date range for the schedule. If set, the schedule only
    # fires on or after start_date and on or before end_date.
    start_date: Mapped[date | None] = mapped_column(Date, nullable=True)
    end_date: Mapped[date | None] = mapped_column(Date, nullable=True)
    # When True, only the month+day of start_date/end_date are used;
    # the window repeats every year rather than expiring after one pass.
    repeat_annually: Mapped[bool] = mapped_column(default=False, nullable=False)

    next_run_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    last_run_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)

    # Optional icon key override (e.g. "sofa", "music"). Null means derive the
    # icon from trigger_type and time_of_day, which is the default behaviour.
    icon: Mapped[str | None] = mapped_column(String(50), nullable=True)

    device: Mapped["Device"] = relationship(back_populates="schedules")
    action: Mapped["Action"] = relationship(back_populates="schedules")
    executions: Mapped[list["ScheduleExecution"]] = relationship(
        back_populates="schedule", cascade="all, delete-orphan", passive_deletes=True
    )

    __table_args__ = (
        Index("ix_schedules_next_run_at", "next_run_at"),
        Index("ix_schedules_device_id", "device_id"),
        Index("ix_schedules_action_id", "action_id"),
        CheckConstraint(
            "(trigger_type != 'time') OR (time_of_day IS NOT NULL)",
            name="ck_schedule_time_requires_time_of_day",
        ),
        CheckConstraint(
            "(trigger_type = 'time') OR (offset_minutes IS NOT NULL)",
            name="ck_schedule_sun_requires_offset",
        ),
        CheckConstraint(
            "days_of_week >= 0 AND days_of_week <= 127",
            name="ck_schedule_days_of_week_range",
        ),
        CheckConstraint(
            "repeat_annually OR end_date IS NULL OR start_date IS NULL OR end_date >= start_date",
            name="ck_schedule_date_range_valid",
        ),
        CheckConstraint(
            "trigger_type IN ('time', 'sunrise', 'sunset')", name="ck_schedule_trigger_type_valid"
        ),
    )

    def __repr__(self) -> str:
        return f"Schedule(id={self.id!r}, name={self.name!r}, enabled={self.enabled!r})"


class ScheduleExecution(Base):
    __tablename__ = "schedule_executions"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=generate_uuid)
    schedule_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("schedules.id", ondelete="CASCADE"), nullable=False
    )
    device_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("devices.id", ondelete="CASCADE"), nullable=False
    )
    fired_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow, nullable=False)
    status: Mapped[ExecutionStatus] = mapped_column(_enum_values(ExecutionStatus), nullable=False)
    # SUCCESS / FAILED: a real attempt was made to reach the device.
    # SKIPPED: the scheduler deliberately did not attempt it (a missed
    # schedule with Settings.catch_up_missed off). error_message is
    # reused for the human-readable reason in this case, and
    # request_payload stays null since nothing was actually sent.
    error_message: Mapped[str | None] = mapped_column(Text, nullable=True)

    # Snapshot of what was actually POSTed to the device, kept so a
    # failure can be debugged later without needing to reproduce it.
    request_payload: Mapped[dict | None] = mapped_column(JSON, nullable=True)

    schedule: Mapped["Schedule"] = relationship(back_populates="executions")
    device: Mapped["Device"] = relationship(back_populates="executions")

    __table_args__ = (
        Index("ix_schedule_executions_fired_at", "fired_at"),
        CheckConstraint(
            "status IN ('success', 'failed', 'skipped')", name="ck_schedule_execution_status_valid"
        ),
    )

    def __repr__(self) -> str:
        return (
            f"ScheduleExecution(id={self.id!r}, status={self.status!r}, "
            f"fired_at={self.fired_at!r})"
        )
