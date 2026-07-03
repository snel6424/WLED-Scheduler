"""schedule device many to many

Revision ID: f98c3f249b98
Revises: 28a7e238df0c
Create Date: 2026-07-01 00:00:00.000000

Replaces schedules.device_id (a single required FK) with a
schedule_devices join table, so one schedule can target several
devices. Paired with that: schedule_executions used to be one row per
(schedule, device) firing; it's now one row per schedule firing, with
a device_results JSON column (a list of {device_id, status,
error_message}) covering every device that schedule targeted at that
moment. The old device_id/status/error_message columns on
schedule_executions are dropped in favor of that.
"""
import json
from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

# revision identifiers, used by Alembic.
revision: str = 'f98c3f249b98'
down_revision: str | Sequence[str] | None = '28a7e238df0c'
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    """Upgrade schema."""
    connection = op.get_bind()

    # --- schedules.device_id -> schedule_devices join table ---
    op.create_table(
        'schedule_devices',
        sa.Column('schedule_id', sa.String(length=36), nullable=False),
        sa.Column('device_id', sa.String(length=36), nullable=False),
        sa.ForeignKeyConstraint(['schedule_id'], ['schedules.id'], ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['device_id'], ['devices.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('schedule_id', 'device_id'),
    )
    connection.execute(
        sa.text(
            "INSERT INTO schedule_devices (schedule_id, device_id) "
            "SELECT id, device_id FROM schedules WHERE device_id IS NOT NULL"
        )
    )
    with op.batch_alter_table('schedules', schema=None) as batch_op:
        batch_op.drop_index('ix_schedules_device_id')
        batch_op.drop_column('device_id')

    # --- schedule_executions: device_id/status/error_message -> device_results ---
    with op.batch_alter_table('schedule_executions', schema=None) as batch_op:
        batch_op.add_column(sa.Column('device_results', sa.JSON(), nullable=True))

    rows = connection.execute(
        sa.text('SELECT id, device_id, status, error_message FROM schedule_executions')
    ).fetchall()
    for row in rows:
        device_results = json.dumps(
            [{'device_id': row.device_id, 'status': row.status, 'error_message': row.error_message}]
        )
        connection.execute(
            sa.text('UPDATE schedule_executions SET device_results = :dr WHERE id = :id'),
            {'dr': device_results, 'id': row.id},
        )

    with op.batch_alter_table('schedule_executions', schema=None) as batch_op:
        batch_op.alter_column('device_results', existing_type=sa.JSON(), nullable=False)
        batch_op.drop_constraint('ck_schedule_execution_status_valid', type_='check')
        batch_op.drop_column('status')
        batch_op.drop_column('error_message')
        batch_op.drop_column('device_id')


def downgrade() -> None:
    """Downgrade schema.

    The schema being downgraded to can only represent one device per
    schedule and one device per execution row. Both are checked
    explicitly and refused with a clear error rather than silently
    dropping data, same approach as f98f29b0e74d's downgrade.
    """
    connection = op.get_bind()

    multi_device_schedules = connection.execute(
        sa.text(
            "SELECT schedule_id, COUNT(*) AS n FROM schedule_devices "
            "GROUP BY schedule_id HAVING COUNT(*) != 1"
        )
    ).fetchall()
    if multi_device_schedules:
        raise RuntimeError(
            f"Cannot downgrade: {len(multi_device_schedules)} schedule(s) target "
            "zero or more than one device, which the schema being downgraded to "
            "cannot represent (device_id is a single required column). Delete or "
            "reduce those schedules to exactly one device first."
        )

    multi_device_executions = connection.execute(
        sa.text(
            "SELECT id FROM schedule_executions WHERE json_array_length(device_results) != 1"
        )
    ).fetchall()
    if multi_device_executions:
        raise RuntimeError(
            f"Cannot downgrade: {len(multi_device_executions)} schedule_executions row(s) "
            "cover zero or more than one device, which the schema being downgraded to "
            "cannot represent (one device_id/status per row). Delete those execution "
            "rows first."
        )

    with op.batch_alter_table('schedule_executions', schema=None) as batch_op:
        batch_op.add_column(sa.Column('device_id', sa.String(length=36), nullable=True))
        batch_op.add_column(
            sa.Column('status', sa.Enum('success', 'failed', 'skipped', name='executionstatus'), nullable=True)
        )
        batch_op.add_column(sa.Column('error_message', sa.Text(), nullable=True))

    rows = connection.execute(
        sa.text('SELECT id, device_results FROM schedule_executions')
    ).fetchall()
    for row in rows:
        (result,) = json.loads(row.device_results)
        connection.execute(
            sa.text(
                'UPDATE schedule_executions SET device_id = :did, status = :status, '
                'error_message = :err WHERE id = :id'
            ),
            {
                'did': result['device_id'],
                'status': result['status'],
                'err': result.get('error_message'),
                'id': row.id,
            },
        )

    with op.batch_alter_table('schedule_executions', schema=None) as batch_op:
        batch_op.alter_column('device_id', existing_type=sa.String(length=36), nullable=False)
        batch_op.alter_column('status', existing_type=sa.Enum(
            'success', 'failed', 'skipped', name='executionstatus'
        ), nullable=False)
        batch_op.create_check_constraint(
            'ck_schedule_execution_status_valid', "status IN ('success', 'failed', 'skipped')"
        )
        batch_op.create_foreign_key(
            'fk_schedule_executions_device_id', 'devices', ['device_id'], ['id'], ondelete='CASCADE'
        )
        batch_op.drop_column('device_results')

    with op.batch_alter_table('schedules', schema=None) as batch_op:
        batch_op.add_column(sa.Column('device_id', sa.String(length=36), nullable=True))

    connection.execute(
        sa.text(
            'UPDATE schedules SET device_id = ('
            'SELECT device_id FROM schedule_devices WHERE schedule_devices.schedule_id = schedules.id'
            ')'
        )
    )

    with op.batch_alter_table('schedules', schema=None) as batch_op:
        batch_op.alter_column('device_id', existing_type=sa.String(length=36), nullable=False)
        batch_op.create_foreign_key(
            'fk_schedules_device_id', 'devices', ['device_id'], ['id'], ondelete='CASCADE'
        )
        batch_op.create_index('ix_schedules_device_id', ['device_id'], unique=False)

    op.drop_table('schedule_devices')
