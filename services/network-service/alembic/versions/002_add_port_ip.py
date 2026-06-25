"""add ip_address to ports

Revision ID: 002_add_port_ip
Revises: 001_initial_network_schema
Create Date: 2026-06-25
"""
from alembic import op
import sqlalchemy as sa

revision = "002_add_port_ip"
down_revision = "001_initial_network_schema"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("ports", sa.Column("ip_address", sa.String(length=45), nullable=True))


def downgrade() -> None:
    op.drop_column("ports", "ip_address")
