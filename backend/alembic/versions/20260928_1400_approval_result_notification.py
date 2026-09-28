"""add approval_result notification type"""
from alembic import op

revision = '20260928_1400_approval_result_notification'
down_revision = '20260928_1300_approval_requests'
branch_labels = None
depends_on = None


def upgrade():
    op.execute(
        "ALTER TABLE notifications MODIFY COLUMN type "
        "ENUM('quota_low','quota_increase','quota_decrease','daily_report','system',"
        "'user_registered','approval_result') NOT NULL"
    )


def downgrade():
    op.execute(
        "ALTER TABLE notifications MODIFY COLUMN type "
        "ENUM('quota_low','quota_increase','quota_decrease','daily_report','system',"
        "'user_registered') NOT NULL"
    )
