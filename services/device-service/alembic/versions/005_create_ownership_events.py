"""Create ownership_events audit table (GDPR accountability)

Revision ID: 005_create_ownership_events
Revises: 004_create_device_consents
Create Date: 2026-06-25
"""
from alembic import op
import sqlalchemy as sa

revision = '005_create_ownership_events'
down_revision = '004_create_device_consents'
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        'ownership_events',
        sa.Column('id', sa.CHAR(36), nullable=False),
        sa.Column('device_id', sa.CHAR(36), nullable=False),
        sa.Column('actor_id', sa.CHAR(36), nullable=False),
        sa.Column('action', sa.String(50), nullable=False),
        sa.Column('details', sa.JSON(), nullable=True),
        sa.Column('created_at', sa.DateTime(), nullable=False),
        sa.PrimaryKeyConstraint('id'),
        mysql_engine='InnoDB',
        mysql_charset='utf8mb4',
        mysql_collate='utf8mb4_unicode_ci',
    )
    op.create_index('ix_ownership_event_id', 'ownership_events', ['id'])
    op.create_index('ix_ownership_event_device_id', 'ownership_events', ['device_id'])
    op.create_index('idx_ownership_event_device_ts', 'ownership_events', ['device_id', 'created_at'])


def downgrade() -> None:
    op.drop_index('idx_ownership_event_device_ts', table_name='ownership_events')
    op.drop_index('ix_ownership_event_device_id', table_name='ownership_events')
    op.drop_index('ix_ownership_event_id', table_name='ownership_events')
    op.drop_table('ownership_events')
