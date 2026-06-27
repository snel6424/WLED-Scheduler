"""add repeat_annually to schedules

Revision ID: c9d3e1f2a4b8
Revises: 42e5ebeca1ff
Create Date: 2026-06-26 12:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = 'c9d3e1f2a4b8'
down_revision: Union[str, Sequence[str], None] = '42e5ebeca1ff'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    with op.batch_alter_table("schedules", schema=None) as batch_op:
        batch_op.add_column(sa.Column("repeat_annually", sa.Boolean(), nullable=False, server_default="0"))
        # Replace the old date-range check (which disallowed end < start) with one
        # that allows cross-year windows when repeat_annually is set.
        batch_op.drop_constraint("ck_schedule_date_range_valid")
        batch_op.create_check_constraint(
            "ck_schedule_date_range_valid",
            "repeat_annually OR end_date IS NULL OR start_date IS NULL OR end_date >= start_date",
        )


def downgrade() -> None:
    with op.batch_alter_table("schedules", schema=None) as batch_op:
        batch_op.drop_constraint("ck_schedule_date_range_valid")
        batch_op.create_check_constraint(
            "ck_schedule_date_range_valid",
            "end_date IS NULL OR start_date IS NULL OR end_date >= start_date",
        )
        batch_op.drop_column("repeat_annually")
