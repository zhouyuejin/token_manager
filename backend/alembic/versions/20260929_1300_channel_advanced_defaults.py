"""Restore server defaults for legacy channel inserts."""
from alembic import op
import sqlalchemy as sa


revision = "20260929_1300_channel_advanced_defaults"
down_revision = "20260929_1200_content_privacy"
branch_labels = None
depends_on = None


def upgrade():
    op.alter_column(
        "channels", "upstream_format", existing_type=sa.String(32),
        existing_nullable=False, server_default="chat",
    )
    op.alter_column(
        "channels", "auth_type", existing_type=sa.String(32),
        existing_nullable=False, server_default="auto",
    )
    op.execute(
        "ALTER TABLE notifications MODIFY COLUMN type "
        "ENUM('quota_low','quota_increase','quota_decrease','daily_report','system',"
        "'user_registered','approval_result','approval_update') NOT NULL"
    )


def downgrade():
    op.execute(
        "ALTER TABLE notifications MODIFY COLUMN type "
        "ENUM('quota_low','quota_increase','quota_decrease','daily_report','system',"
        "'user_registered','approval_result') NOT NULL"
    )
    op.alter_column(
        "channels", "auth_type", existing_type=sa.String(32),
        existing_nullable=False, server_default=None,
    )
    op.alter_column(
        "channels", "upstream_format", existing_type=sa.String(32),
        existing_nullable=False, server_default=None,
    )
