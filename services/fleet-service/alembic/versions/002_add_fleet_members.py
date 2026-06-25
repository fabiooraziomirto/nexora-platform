"""add fleet_members table

Revision ID: 002_add_fleet_members
Revises: 001_initial_fleet_schema
Create Date: 2026-06-25
"""
from alembic import op
import sqlalchemy as sa

revision = "002_add_fleet_members"
down_revision = "001_initial_fleet_schema"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "fleet_members",
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.Column("fleet_id", sa.String(length=36), nullable=False),
        sa.Column("device_id", sa.String(length=64), nullable=False),
        sa.Column("joined_at", sa.DateTime(), nullable=True),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("fleet_id", "device_id", name="uq_fleet_member"),
    )
    op.create_index(op.f("ix_fleet_members_fleet_id"), "fleet_members", ["fleet_id"], unique=False)
    op.create_index(op.f("ix_fleet_members_device_id"), "fleet_members", ["device_id"], unique=False)


def downgrade() -> None:
    op.drop_index(op.f("ix_fleet_members_device_id"), table_name="fleet_members")
    op.drop_index(op.f("ix_fleet_members_fleet_id"), table_name="fleet_members")
    op.drop_table("fleet_members")
