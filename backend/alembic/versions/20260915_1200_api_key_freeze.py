"""API Key automatic freeze metadata."""
from alembic import op
import sqlalchemy as sa

revision = '20260915_1200_api_key_freeze'
down_revision = '20260915_1100_api_key_rate_limits'
branch_labels = None
depends_on = None


def upgrade():
    op.add_column('api_keys', sa.Column('frozen_at', sa.DateTime(), nullable=True, comment='自动冻结时间'))
    op.add_column('api_keys', sa.Column('frozen_reason', sa.String(255), nullable=True, comment='自动冻结原因'))
    # 保留本地已部署迁移的兼容字段；本任务使用管理员解除的 disabled 冻结。
    op.add_column('api_keys', sa.Column('frozen_until', sa.DateTime(), nullable=True, comment='冻结截止时间'))


def downgrade():
    op.drop_column('api_keys', 'frozen_until')
    op.drop_column('api_keys', 'frozen_reason')
    op.drop_column('api_keys', 'frozen_at')
