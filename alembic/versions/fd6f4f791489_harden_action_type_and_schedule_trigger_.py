"""harden action type and schedule trigger_type with check constraints

Revision ID: fd6f4f791489
Revises: f98f29b0e74d
Create Date: 2026-06-25 03:45:32.442828

"""
from collections.abc import Sequence

from alembic import op

# revision identifiers, used by Alembic.
revision: str = 'fd6f4f791489'
down_revision: str | Sequence[str] | None = 'f98f29b0e74d'
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    """Upgrade schema."""
    # Same root cause as the previous migration: sa.Enum on SQLite
    # never created a real CHECK constraint here either. These two
    # columns are simpler to fix than status was, since the set of
    # valid values isn't changing, only going from unenforced to
    # enforced, so no batch_alter_table type change is needed, just
    # adding the constraints.
    with op.batch_alter_table("actions", schema=None) as batch_op:
        batch_op.create_check_constraint("ck_action_type_valid", "type IN ('preset', 'state')")

    with op.batch_alter_table("schedules", schema=None) as batch_op:
        batch_op.create_check_constraint(
            "ck_schedule_trigger_type_valid", "trigger_type IN ('time', 'sunrise', 'sunset')"
        )


def downgrade() -> None:
    """Downgrade schema."""
    # Nothing to check for here, unlike the status migration: every
    # value either column has ever been able to hold (via the
    # application layer) is still valid under the narrower, unenforced
    # schema being downgraded to. There's no possible incompatible row.
    with op.batch_alter_table("schedules", schema=None) as batch_op:
        batch_op.drop_constraint("ck_schedule_trigger_type_valid", type_="check")

    with op.batch_alter_table("actions", schema=None) as batch_op:
        batch_op.drop_constraint("ck_action_type_valid", type_="check")
