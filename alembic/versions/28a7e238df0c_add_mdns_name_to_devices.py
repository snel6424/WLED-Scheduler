"""add_mdns_name_to_devices

Revision ID: 28a7e238df0c
Revises: 3a7f91c0d824
Create Date: 2026-07-01 15:30:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '28a7e238df0c'
down_revision: Union[str, Sequence[str], None] = '3a7f91c0d824'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    with op.batch_alter_table('devices', schema=None) as batch_op:
        batch_op.add_column(sa.Column('mdns_name', sa.String(length=255), nullable=True))
        batch_op.create_unique_constraint('uq_devices_mdns_name', ['mdns_name'])


def downgrade() -> None:
    with op.batch_alter_table('devices', schema=None) as batch_op:
        batch_op.drop_constraint('uq_devices_mdns_name', type_='unique')
        batch_op.drop_column('mdns_name')
