"""add hostname and tls_enabled to webservices

Revision ID: 002_add_webservice_hostname
Revises: 001_initial_webservice_schema
Create Date: 2026-06-25
"""
from alembic import op
import sqlalchemy as sa

revision = "002_add_webservice_hostname"
down_revision = "001_initial_webservice_schema"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("webservices", sa.Column("hostname", sa.String(length=255), nullable=True))
    op.add_column("webservices", sa.Column("tls_enabled", sa.Boolean(), nullable=True, server_default="1"))


def downgrade() -> None:
    op.drop_column("webservices", "tls_enabled")
    op.drop_column("webservices", "hostname")
