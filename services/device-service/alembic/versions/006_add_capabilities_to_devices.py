"""Add capabilities field to devices for FaaS edge runtime support

Revision ID: 006_add_capabilities_to_devices
Revises: 005_create_ownership_events
Create Date: 2026-06-25
"""
from alembic import op
import sqlalchemy as sa

revision = "006_add_capabilities_to_devices"
down_revision = "005_create_ownership_events"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("devices", sa.Column("capabilities", sa.Text(), nullable=True))


def downgrade() -> None:
    op.drop_column("devices", "capabilities")
