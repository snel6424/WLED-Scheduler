"""add powered_on to devices

Revision ID: d4e7f1a2b3c9
Revises: c9d3e1f2a4b8
Create Date: 2026-06-27 12:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = 'd4e7f1a2b3c9'
down_revision: Union[str, Sequence[str], None] = 'c9d3e1f2a4b8'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    with op.batch_alter_table("devices", schema=None) as batch_op:
        batch_op.add_column(sa.Column("powered_on", sa.Boolean(), nullable=True))


def downgrade() -> None:
    with op.batch_alter_table("devices", schema=None) as batch_op:
        batch_op.drop_column("powered_on")
