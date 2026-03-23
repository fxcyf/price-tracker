"""Add in_stock column to products

Revision ID: 0006
Revises: 0005
Create Date: 2026-03-22

"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "0006"
down_revision: Union[str, None] = "0005"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column("products", sa.Column("in_stock", sa.Boolean(), nullable=True))


def downgrade() -> None:
    op.drop_column("products", "in_stock")
