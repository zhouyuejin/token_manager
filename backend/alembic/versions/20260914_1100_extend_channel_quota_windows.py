"""
extend_channel_quota_windows

Allow channel quota records to store provider-defined time windows such as
five_hour, daily, monthly, and custom.

Revision ID: 20260914_1100_extend_channel_quota_windows
Revises: 20260911_0924_add_channel_advanced_config
Create Date: 2026-09-14 11:00:00
"""
from alembic import op

revision = '20260914_1100_extend_channel_quota_windows'
down_revision = '20260911_0924_add_channel_advanced_config'
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute(
        "ALTER TABLE channel_quotas "
        "MODIFY COLUMN quota_type "
        "ENUM('hourly','five_hour','daily','weekly','monthly','custom') NOT NULL "
        "COMMENT '配额窗口类型'"
    )


def downgrade() -> None:
    op.execute("DELETE FROM channel_quotas WHERE quota_type NOT IN ('hourly','weekly')")
    op.execute(
        "ALTER TABLE channel_quotas "
        "MODIFY COLUMN quota_type "
        "ENUM('hourly','weekly') NOT NULL "
        "COMMENT '配额类型'"
    )
