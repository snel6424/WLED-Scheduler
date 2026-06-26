"""add schedule date range

Revision ID: 42e5ebeca1ff
Revises: 40cc2a1822a0
Create Date: 2026-06-26 07:37:43.290160

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '42e5ebeca1ff'
down_revision: Union[str, Sequence[str], None] = '40cc2a1822a0'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    with op.batch_alter_table("schedules", schema=None) as batch_op:
        batch_op.add_column(sa.Column("start_date", sa.Date(), nullable=True))
        batch_op.add_column(sa.Column("end_date", sa.Date(), nullable=True))
        batch_op.create_check_constraint(
            "ck_schedule_date_range_valid",
            "end_date IS NULL OR start_date IS NULL OR end_date >= start_date",
        )


def downgrade() -> None:
    """Downgrade schema."""
    with op.batch_alter_table("schedules", schema=None) as batch_op:
        batch_op.drop_constraint("ck_schedule_date_range_valid")
        batch_op.drop_column("end_date")
        batch_op.drop_column("start_date")
