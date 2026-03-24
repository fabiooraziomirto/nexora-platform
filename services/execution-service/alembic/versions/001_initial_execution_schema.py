"""initial execution schema

Revision ID: 001_initial_execution_schema
Revises:
Create Date: 2026-03-23
"""
from alembic import op
import sqlalchemy as sa

revision = "001_initial_execution_schema"
down_revision = None
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "executions",
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.Column("device_id", sa.String(length=64), nullable=True),
        sa.Column("command", sa.String(length=255), nullable=False, server_default="noop"),
        sa.Column("status", sa.String(length=64), nullable=False, server_default="queued"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(op.f("ix_executions_id"), "executions", ["id"], unique=False)
    op.create_index(op.f("ix_executions_device_id"), "executions", ["device_id"], unique=False)


def downgrade() -> None:
    op.drop_index(op.f("ix_executions_device_id"), table_name="executions")
    op.drop_index(op.f("ix_executions_id"), table_name="executions")
    op.drop_table("executions")
