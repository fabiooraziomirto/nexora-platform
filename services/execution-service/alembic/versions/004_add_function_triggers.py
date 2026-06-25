"""add function_triggers table

Revision ID: 004_add_function_triggers
Revises: 003_add_faas_fields_to_executions
Create Date: 2026-06-25
"""
from alembic import op
import sqlalchemy as sa

revision = "004_add_function_triggers"
down_revision = "003_add_faas_fields_to_executions"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "function_triggers",
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.Column("event_type", sa.String(length=100), nullable=False),
        sa.Column("function_id", sa.String(length=36), nullable=False),
        sa.Column("target_type", sa.String(length=20), nullable=False, server_default="same_device"),
        sa.Column("target_id", sa.String(length=36), nullable=True),
        sa.Column("filter_expr", sa.Text(), nullable=True),
        sa.Column("is_active", sa.Boolean(), nullable=False, server_default="1"),
        sa.Column("tenant_id", sa.String(length=64), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=True),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(op.f("ix_function_triggers_event_type"), "function_triggers", ["event_type"])
    op.create_index(op.f("ix_function_triggers_function_id"), "function_triggers", ["function_id"])
    op.create_index(op.f("ix_function_triggers_tenant_id"), "function_triggers", ["tenant_id"])


def downgrade() -> None:
    op.drop_index(op.f("ix_function_triggers_tenant_id"), table_name="function_triggers")
    op.drop_index(op.f("ix_function_triggers_function_id"), table_name="function_triggers")
    op.drop_index(op.f("ix_function_triggers_event_type"), table_name="function_triggers")
    op.drop_table("function_triggers")
