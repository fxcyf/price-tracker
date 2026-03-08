"""Move schedule settings to global settings table

Revision ID: 0004
Revises: 0003
Create Date: 2026-03-08
"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "0004"
down_revision: Union[str, None] = "0003"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Add global schedule columns to settings
    op.add_column("settings", sa.Column(
        "check_interval_hours", sa.Integer(), nullable=False, server_default="24"
    ))
    op.add_column("settings", sa.Column(
        "alert_on_rise", sa.Boolean(), nullable=False, server_default="false"
    ))

    # Drop per-product columns from watch_configs
    op.drop_column("watch_configs", "check_interval_hours")
    op.drop_column("watch_configs", "alert_on_rise")


def downgrade() -> None:
    op.add_column("watch_configs", sa.Column(
        "alert_on_rise", sa.Boolean(), nullable=False, server_default="false"
    ))
    op.add_column("watch_configs", sa.Column(
        "check_interval_hours", sa.Integer(), nullable=False, server_default="6"
    ))
    op.drop_column("settings", "alert_on_rise")
    op.drop_column("settings", "check_interval_hours")
