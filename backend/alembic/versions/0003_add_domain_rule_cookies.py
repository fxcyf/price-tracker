"""Add cookies fields to domain_rules

Revision ID: 0003
Revises: 0002
Create Date: 2026-03-08

"""
from typing import Sequence, Union

import sqlalchemy as sa
from sqlalchemy.dialects import postgresql
from alembic import op

revision: str = "0003"
down_revision: Union[str, None] = "0002"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column("domain_rules", sa.Column("cookies", postgresql.JSONB(), nullable=True))
    op.add_column("domain_rules", sa.Column(
        "cookies_status", sa.String(20), nullable=False, server_default="none"
    ))
    op.add_column("domain_rules", sa.Column(
        "cookies_updated_at", sa.DateTime(timezone=True), nullable=True
    ))


def downgrade() -> None:
    op.drop_column("domain_rules", "cookies_updated_at")
    op.drop_column("domain_rules", "cookies_status")
    op.drop_column("domain_rules", "cookies")
