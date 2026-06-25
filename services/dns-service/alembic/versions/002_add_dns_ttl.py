"""add ttl to dns_records

Revision ID: 002_add_dns_ttl
Revises: 001_initial_dns_schema
Create Date: 2026-06-25
"""
from alembic import op
import sqlalchemy as sa

revision = "002_add_dns_ttl"
down_revision = "001_initial_dns_schema"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("dns_records", sa.Column("ttl", sa.Integer(), nullable=True, server_default="300"))


def downgrade() -> None:
    op.drop_column("dns_records", "ttl")
