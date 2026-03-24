"""initial dns schema

Revision ID: 001_initial_dns_schema
Revises:
Create Date: 2026-03-23
"""
from alembic import op
import sqlalchemy as sa

revision = "001_initial_dns_schema"
down_revision = None
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "dns_records",
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.Column("name", sa.String(length=255), nullable=False),
        sa.Column("type", sa.String(length=16), nullable=False, server_default="A"),
        sa.Column("value", sa.String(length=255), nullable=True),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(op.f("ix_dns_records_id"), "dns_records", ["id"], unique=False)
    op.create_index(op.f("ix_dns_records_name"), "dns_records", ["name"], unique=False)


def downgrade() -> None:
    op.drop_index(op.f("ix_dns_records_name"), table_name="dns_records")
    op.drop_index(op.f("ix_dns_records_id"), table_name="dns_records")
    op.drop_table("dns_records")
