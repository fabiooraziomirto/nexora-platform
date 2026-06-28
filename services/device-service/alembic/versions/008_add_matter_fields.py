"""Add connection_protocol, protocol_meta to devices; add unit to device_telemetry

Revision ID: 008_add_matter_fields
Revises: 007_add_runtime_env_to_devices
Create Date: 2026-06-28
"""
from alembic import op
import sqlalchemy as sa

revision = "008_add_matter_fields"
down_revision = "007_add_runtime_env_to_devices"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "devices",
        sa.Column(
            "connection_protocol",
            sa.String(50),
            nullable=False,
            server_default="nexora-agent",
        ),
    )
    op.create_index("idx_device_protocol", "devices", ["connection_protocol"])

    op.add_column("devices", sa.Column("protocol_meta", sa.JSON(), nullable=True))

    op.add_column(
        "device_telemetry",
        sa.Column("unit", sa.String(32), nullable=True),
    )


def downgrade() -> None:
    op.drop_column("device_telemetry", "unit")
    op.drop_column("devices", "protocol_meta")
    op.drop_index("idx_device_protocol", table_name="devices")
    op.drop_column("devices", "connection_protocol")
