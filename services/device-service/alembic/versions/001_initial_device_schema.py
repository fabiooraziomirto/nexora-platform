"""Revision ID: 001_initial_device_schema
Revises: 
Create Date: 2024-01-XX

"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import mysql

# revision identifiers, used by Alembic.
revision = '001_initial_device_schema'
down_revision = None
branch_labels = None
depends_on = None


def upgrade() -> None:
    """Create devices table."""
    op.create_table(
        'devices',
        sa.Column('id', sa.CHAR(36), nullable=False),
        sa.Column('name', sa.String(255), nullable=False),
        sa.Column('device_type', sa.String(100), nullable=False),
        sa.Column('description', sa.Text(), nullable=True),
        sa.Column('status', sa.String(50), nullable=False, server_default='offline'),
        sa.Column('last_seen', sa.DateTime(), nullable=True),
        sa.Column('metadata', sa.JSON(), nullable=True),
        sa.Column('tags', sa.JSON(), nullable=True),
        sa.Column('created_at', sa.DateTime(), nullable=False),
        sa.Column('updated_at', sa.DateTime(), nullable=False),
        sa.PrimaryKeyConstraint('id'),
        mysql_engine='InnoDB',
        mysql_charset='utf8mb4',
        mysql_collate='utf8mb4_unicode_ci'
    )
    
    # Create indexes
    op.create_index('idx_device_status_updated', 'devices', ['status', 'updated_at'])
    op.create_index('idx_device_name_type', 'devices', ['name', 'device_type'])
    op.create_index(op.f('ix_devices_id'), 'devices', ['id'])
    op.create_index(op.f('ix_devices_name'), 'devices', ['name'])
    op.create_index(op.f('ix_devices_status'), 'devices', ['status'])
    op.create_index(op.f('ix_devices_last_seen'), 'devices', ['last_seen'])


def downgrade() -> None:
    """Drop devices table."""
    op.drop_index(op.f('ix_devices_last_seen'), table_name='devices')
    op.drop_index(op.f('ix_devices_status'), table_name='devices')
    op.drop_index(op.f('ix_devices_name'), table_name='devices')
    op.drop_index(op.f('ix_devices_id'), table_name='devices')
    op.drop_index('idx_device_name_type', table_name='devices')
    op.drop_index('idx_device_status_updated', table_name='devices')
    op.drop_table('devices')

