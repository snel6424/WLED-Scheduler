"""add preset to schedule_devices

Revision ID: a3f5c8d1e6b2
Revises: f98c3f249b98
Create Date: 2026-07-11 00:00:00.000000

Adds a nullable per-device preset override to the schedule_devices
join table, so a multi-device preset schedule can fire a different
preset number on each device. NULL (every existing row, and any
single-device preset schedule that hasn't been re-saved since this
column existed) means "no override"; app.view_helpers.effective_device_preset
falls back to the Action's own shared `ps` in that case, so this is a
purely additive change, no backfill needed.
"""
from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

# revision identifiers, used by Alembic.
revision: str = 'a3f5c8d1e6b2'
down_revision: str | Sequence[str] | None = 'f98c3f249b98'
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    """Upgrade schema."""
    with op.batch_alter_table('schedule_devices', schema=None) as batch_op:
        batch_op.add_column(sa.Column('preset', sa.Integer(), nullable=True))


def downgrade() -> None:
    """Downgrade schema."""
    with op.batch_alter_table('schedule_devices', schema=None) as batch_op:
        batch_op.drop_column('preset')
