"""Add owner_id, tenant_id, privacy_level to devices

Revision ID: 002_add_ownership_to_devices
Revises: 001_initial_device_schema
Create Date: 2026-06-25
"""
from alembic import op
import sqlalchemy as sa

revision = '002_add_ownership_to_devices'
down_revision = '001_initial_device_schema'
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column('devices', sa.Column('owner_id', sa.CHAR(36), nullable=True))
    op.add_column('devices', sa.Column('tenant_id', sa.String(255), nullable=True))
    op.add_column('devices', sa.Column('privacy_level', sa.Integer(), nullable=False, server_default='0'))
    op.create_index('ix_devices_owner_id', 'devices', ['owner_id'])
    op.create_index('ix_devices_tenant_id', 'devices', ['tenant_id'])
    op.create_index('idx_device_owner_tenant', 'devices', ['owner_id', 'tenant_id'])


def downgrade() -> None:
    op.drop_index('idx_device_owner_tenant', table_name='devices')
    op.drop_index('ix_devices_tenant_id', table_name='devices')
    op.drop_index('ix_devices_owner_id', table_name='devices')
    op.drop_column('devices', 'privacy_level')
    op.drop_column('devices', 'tenant_id')
    op.drop_column('devices', 'owner_id')
