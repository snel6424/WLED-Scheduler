"""add skipped status to scheduleexecution

Revision ID: f98f29b0e74d
Revises: e52f713d398e
Create Date: 2026-06-25 03:42:30.432187

"""
from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

# revision identifiers, used by Alembic.
revision: str = 'f98f29b0e74d'
down_revision: str | Sequence[str] | None = 'e52f713d398e'
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    """Upgrade schema."""
    # Autogenerate doesn't reliably detect Enum value changes on an
    # existing column (only at table creation), so this is hand-written.
    # SQLite has no native enum type; sa.Enum renders as a plain
    # VARCHAR with NO actual CHECK constraint by default (confirmed by
    # inspecting the real CREATE TABLE SQL: a bare `status VARCHAR(7)`,
    # nothing enforcing membership). This migration both widens the
    # column and, this time, actually adds a real CHECK constraint,
    # which the original migration should have had and didn't.
    with op.batch_alter_table("schedule_executions", schema=None) as batch_op:
        batch_op.alter_column(
            "status",
            existing_type=sa.Enum("success", "failed", name="executionstatus"),
            type_=sa.Enum("success", "failed", "skipped", name="executionstatus"),
            existing_nullable=False,
        )
        batch_op.create_check_constraint(
            "ck_schedule_execution_status_valid", "status IN ('success', 'failed', 'skipped')"
        )


def downgrade() -> None:
    """Downgrade schema."""
    # The schema being downgraded TO (e52f713d398e) has no CHECK
    # constraint at all on this column, that's the original bug this
    # migration fixes. Which means the database itself can't be relied
    # on to reject incompatible 'skipped' rows during the downgrade;
    # it has to be checked explicitly here instead, or this would
    # silently let bad data through into a schema that doesn't expect it.
    connection = op.get_bind()
    incompatible = connection.execute(
        sa.text("SELECT COUNT(*) FROM schedule_executions WHERE status = 'skipped'")
    ).scalar()
    if incompatible:
        raise RuntimeError(
            f"Cannot downgrade: {incompatible} schedule_executions row(s) have "
            "status='skipped', which is not valid in the schema being downgraded "
            "to. Delete or reassign those rows first."
        )

    with op.batch_alter_table("schedule_executions", schema=None) as batch_op:
        batch_op.drop_constraint("ck_schedule_execution_status_valid", type_="check")
        batch_op.alter_column(
            "status",
            existing_type=sa.Enum("success", "failed", "skipped", name="executionstatus"),
            type_=sa.Enum("success", "failed", name="executionstatus"),
            existing_nullable=False,
        )
