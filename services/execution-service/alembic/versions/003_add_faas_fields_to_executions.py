"""Add FaaS fields to executions (execution_type, plugin_id, args, function_result)

Revision ID: 003_add_faas_fields_to_executions
Revises: 002_add_owner_id_to_executions
Create Date: 2026-06-25
"""
from alembic import op
import sqlalchemy as sa

revision = "003_add_faas_fields_to_executions"
down_revision = "002_add_owner_id_to_executions"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("executions", sa.Column("execution_type", sa.String(30), nullable=True))
    op.add_column("executions", sa.Column("plugin_id", sa.String(36), nullable=True))
    op.add_column("executions", sa.Column("args", sa.Text(), nullable=True))
    op.add_column("executions", sa.Column("function_result", sa.Text(), nullable=True))
    op.add_column("executions", sa.Column("invocation_mode", sa.String(10), nullable=True))
    op.create_index("ix_executions_plugin_id", "executions", ["plugin_id"])


def downgrade() -> None:
    op.drop_index("ix_executions_plugin_id", table_name="executions")
    op.drop_column("executions", "invocation_mode")
    op.drop_column("executions", "function_result")
    op.drop_column("executions", "args")
    op.drop_column("executions", "plugin_id")
    op.drop_column("executions", "execution_type")
