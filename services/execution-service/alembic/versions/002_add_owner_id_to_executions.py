"""Add owner_id to executions for privacy-level enforcement

Revision ID: 002_add_owner_id_to_executions
Revises: 001_initial_execution_schema
Create Date: 2026-06-25
"""
from alembic import op
import sqlalchemy as sa

revision = "002_add_owner_id_to_executions"
down_revision = "001_initial_execution_schema"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("executions", sa.Column("owner_id", sa.String(64), nullable=True))
    op.create_index("ix_executions_owner_id", "executions", ["owner_id"])


def downgrade() -> None:
    op.drop_index("ix_executions_owner_id", table_name="executions")
    op.drop_column("executions", "owner_id")
