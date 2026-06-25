"""Add runtime_env field to devices for FaaS secrets configuration

Revision ID: 007_add_runtime_env_to_devices
Revises: 006_add_capabilities_to_devices
Create Date: 2026-06-25
"""
from alembic import op
import sqlalchemy as sa

revision = "007_add_runtime_env_to_devices"
down_revision = "006_add_capabilities_to_devices"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("devices", sa.Column("runtime_env", sa.Text(), nullable=True))


def downgrade() -> None:
    op.drop_column("devices", "runtime_env")
