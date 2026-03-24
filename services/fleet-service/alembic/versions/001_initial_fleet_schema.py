"""initial fleet schema

Revision ID: 001_initial_fleet_schema
Revises:
Create Date: 2026-03-23
"""
from alembic import op
import sqlalchemy as sa

revision = "001_initial_fleet_schema"
down_revision = None
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "fleets",
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.Column("name", sa.String(length=255), nullable=False),
        sa.Column("description", sa.String(length=1024), nullable=True),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(op.f("ix_fleets_id"), "fleets", ["id"], unique=False)
    op.create_index(op.f("ix_fleets_name"), "fleets", ["name"], unique=False)


def downgrade() -> None:
    op.drop_index(op.f("ix_fleets_name"), table_name="fleets")
    op.drop_index(op.f("ix_fleets_id"), table_name="fleets")
    op.drop_table("fleets")
