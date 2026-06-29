"""add_description_to_schedules

Revision ID: 3a7f91c0d824
Revises: bf72ce13d420
Create Date: 2026-06-28 21:15:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '3a7f91c0d824'
down_revision: Union[str, Sequence[str], None] = 'bf72ce13d420'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    with op.batch_alter_table('schedules', schema=None) as batch_op:
        batch_op.add_column(sa.Column('description', sa.Text(), nullable=True))


def downgrade() -> None:
    with op.batch_alter_table('schedules', schema=None) as batch_op:
        batch_op.drop_column('description')
