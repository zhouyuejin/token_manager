"""Add approval supplement and update notification type."""
from alembic import op
import sqlalchemy as sa

revision = '20260928_1500_approval_supplement'
down_revision = '20260928_1400_approval_result_notification'
branch_labels = None
depends_on = None


def upgrade():
    columns = {column['name'] for column in sa.inspect(op.get_bind()).get_columns('approval_requests')}
    if 'supplement' not in columns:
        op.add_column('approval_requests', sa.Column('supplement', sa.Text(), nullable=True))
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
    op.drop_column('approval_requests', 'supplement')
