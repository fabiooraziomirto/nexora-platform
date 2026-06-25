"""Create device_consents table (opt-in privacy levels)

Revision ID: 004_create_device_consents
Revises: 003_create_device_discoveries
Create Date: 2026-06-25
"""
from alembic import op
import sqlalchemy as sa

revision = '004_create_device_consents'
down_revision = '003_create_device_discoveries'
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        'device_consents',
        sa.Column('id', sa.CHAR(36), nullable=False),
        sa.Column('device_id', sa.CHAR(36), nullable=False),
        sa.Column('granted_by', sa.CHAR(36), nullable=False),
        sa.Column('granted_to', sa.String(255), nullable=False),
        sa.Column('granted_to_type', sa.String(20), nullable=False),
        sa.Column('level', sa.Integer(), nullable=False),
        sa.Column('granted_at', sa.DateTime(), nullable=False),
        sa.Column('revoked_at', sa.DateTime(), nullable=True),
        sa.Column('is_active', sa.Boolean(), nullable=False, server_default='1'),
        sa.PrimaryKeyConstraint('id'),
        mysql_engine='InnoDB',
        mysql_charset='utf8mb4',
        mysql_collate='utf8mb4_unicode_ci',
    )
    op.create_index('ix_consent_id', 'device_consents', ['id'])
    op.create_index('idx_consent_device_active', 'device_consents', ['device_id', 'is_active'])
    op.create_index('idx_consent_granted_to', 'device_consents', ['granted_to', 'granted_to_type', 'is_active'])


def downgrade() -> None:
    op.drop_index('idx_consent_granted_to', table_name='device_consents')
    op.drop_index('idx_consent_device_active', table_name='device_consents')
    op.drop_index('ix_consent_id', table_name='device_consents')
    op.drop_table('device_consents')
