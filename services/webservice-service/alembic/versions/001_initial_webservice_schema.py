"""initial webservice schema

Revision ID: 001_initial_webservice_schema
Revises:
Create Date: 2026-03-23
"""
from alembic import op
import sqlalchemy as sa

revision = "001_initial_webservice_schema"
down_revision = None
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "webservices",
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.Column("device_id", sa.String(length=64), nullable=True),
        sa.Column("port", sa.Integer(), nullable=False, server_default="443"),
        sa.Column("status", sa.String(length=64), nullable=False, server_default="enabled"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(op.f("ix_webservices_id"), "webservices", ["id"], unique=False)
    op.create_index(op.f("ix_webservices_device_id"), "webservices", ["device_id"], unique=False)


def downgrade() -> None:
    op.drop_index(op.f("ix_webservices_device_id"), table_name="webservices")
    op.drop_index(op.f("ix_webservices_id"), table_name="webservices")
    op.drop_table("webservices")
