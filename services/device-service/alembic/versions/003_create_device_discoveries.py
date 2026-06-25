"""Create device_discoveries table (RFC 8628 pairing flow)

Revision ID: 003_create_device_discoveries
Revises: 002_add_ownership_to_devices
Create Date: 2026-06-25
"""
from alembic import op
import sqlalchemy as sa

revision = '003_create_device_discoveries'
down_revision = '002_add_ownership_to_devices'
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        'device_discoveries',
        sa.Column('id', sa.CHAR(36), nullable=False),
        sa.Column('hardware_id', sa.String(255), nullable=False),
        sa.Column('device_type', sa.String(100), nullable=False),
        sa.Column('firmware_version', sa.String(50), nullable=True),
        sa.Column('device_code', sa.String(64), nullable=False),
        sa.Column('user_code', sa.String(16), nullable=False),
        sa.Column('status', sa.String(30), nullable=False, server_default='announced'),
        sa.Column('expires_at', sa.DateTime(), nullable=False),
        sa.Column('claimed_by', sa.CHAR(36), nullable=True),
        sa.Column('claimed_tenant', sa.String(255), nullable=True),
        sa.Column('claimed_at', sa.DateTime(), nullable=True),
        sa.Column('bootstrap_token_issued', sa.String(255), nullable=True),
        sa.Column('device_id', sa.CHAR(36), nullable=True),
        sa.Column('created_at', sa.DateTime(), nullable=False),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('device_code', name='uq_discovery_device_code'),
        sa.UniqueConstraint('user_code', name='uq_discovery_user_code'),
        mysql_engine='InnoDB',
        mysql_charset='utf8mb4',
        mysql_collate='utf8mb4_unicode_ci',
    )
    op.create_index('ix_discovery_id', 'device_discoveries', ['id'])
    op.create_index('ix_discovery_hardware_id', 'device_discoveries', ['hardware_id'])
    op.create_index('ix_discovery_device_code', 'device_discoveries', ['device_code'])
    op.create_index('ix_discovery_user_code', 'device_discoveries', ['user_code'])
    op.create_index('ix_discovery_status', 'device_discoveries', ['status'])
    op.create_index('idx_discovery_status_expires', 'device_discoveries', ['status', 'expires_at'])


def downgrade() -> None:
    op.drop_index('idx_discovery_status_expires', table_name='device_discoveries')
    op.drop_index('ix_discovery_status', table_name='device_discoveries')
    op.drop_index('ix_discovery_user_code', table_name='device_discoveries')
    op.drop_index('ix_discovery_device_code', table_name='device_discoveries')
    op.drop_index('ix_discovery_hardware_id', table_name='device_discoveries')
    op.drop_index('ix_discovery_id', table_name='device_discoveries')
    op.drop_table('device_discoveries')
