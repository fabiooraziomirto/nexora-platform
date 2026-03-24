"""initial network schema

Revision ID: 001_initial_network_schema
Revises:
Create Date: 2026-03-23
"""
from alembic import op
import sqlalchemy as sa

revision = "001_initial_network_schema"
down_revision = None
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "ports",
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.Column("device_id", sa.String(length=64), nullable=True),
        sa.Column("network_id", sa.String(length=64), nullable=True),
        sa.Column("status", sa.String(length=64), nullable=False, server_default="created"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(op.f("ix_ports_id"), "ports", ["id"], unique=False)
    op.create_index(op.f("ix_ports_device_id"), "ports", ["device_id"], unique=False)
    op.create_index(op.f("ix_ports_network_id"), "ports", ["network_id"], unique=False)


def downgrade() -> None:
    op.drop_index(op.f("ix_ports_network_id"), table_name="ports")
    op.drop_index(op.f("ix_ports_device_id"), table_name="ports")
    op.drop_index(op.f("ix_ports_id"), table_name="ports")
    op.drop_table("ports")
