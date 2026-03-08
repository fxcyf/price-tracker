"""Add domain_rules table

Revision ID: 0002
Revises: 0001
Create Date: 2026-03-07

"""
from typing import Sequence, Union

import sqlalchemy as sa
from sqlalchemy.dialects import postgresql
from alembic import op

revision: str = "0002"
down_revision: Union[str, None] = "0001"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "domain_rules",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("domain", sa.String(200), nullable=False),
        sa.Column("price_selector", sa.Text(), nullable=True),
        sa.Column("title_selector", sa.Text(), nullable=True),
        sa.Column("image_selector", sa.Text(), nullable=True),
        sa.Column("success_count", sa.Integer(), nullable=False, server_default="1"),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("domain"),
    )
    op.create_index("ix_domain_rules_domain", "domain_rules", ["domain"])


def downgrade() -> None:
    op.drop_index("ix_domain_rules_domain", "domain_rules")
    op.drop_table("domain_rules")
