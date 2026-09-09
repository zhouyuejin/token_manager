"""drop api_key per-key limit columns (GC-9)

Revision ID: drop_api_key_limit_columns
Revises: admin_quota_unlimited
Create Date: 2026-09-09 12:00:00.000000

变更说明：
架构收敛为 User.quota (USD) 单一限流来源，删 api_keys 表上的 7 个 per-key 限额字段：
- daily_limit / daily_used / daily_reset_at
- monthly_limit / monthly_used / monthly_reset_at
- qps_limit（从未执行过任何检查，纯死代码）

衔接：上一轮已经把 schema/接口/前端的输入侧字段去掉，但响应展示还在，
模型列还在，proxy_service 还有不可达分支。本次一并清掉。

不可逆（drop column）。downgrade 仅按列类型重建空字段，**不回填历史数据**。
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'drop_api_key_limit_columns'
down_revision: Union[str, None] = 'admin_quota_unlimited'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """删 api_keys 表的 7 个 per-key 限额列。"""
    op.drop_column('api_keys', 'daily_limit')
    op.drop_column('api_keys', 'daily_used')
    op.drop_column('api_keys', 'daily_reset_at')
    op.drop_column('api_keys', 'monthly_limit')
    op.drop_column('api_keys', 'monthly_used')
    op.drop_column('api_keys', 'monthly_reset_at')
    op.drop_column('api_keys', 'qps_limit')


def downgrade() -> None:
    """回滚：重建列（默认值 0 / NULL），不回填历史数据。"""
    op.add_column('api_keys', sa.Column('daily_limit', sa.BigInteger(), nullable=True, server_default='0'))
    op.add_column('api_keys', sa.Column('daily_used', sa.BigInteger(), nullable=True, server_default='0'))
    op.add_column('api_keys', sa.Column('daily_reset_at', sa.DateTime(), nullable=True))
    op.add_column('api_keys', sa.Column('monthly_limit', sa.BigInteger(), nullable=True, server_default='0'))
    op.add_column('api_keys', sa.Column('monthly_used', sa.BigInteger(), nullable=True, server_default='0'))
    op.add_column('api_keys', sa.Column('monthly_reset_at', sa.DateTime(), nullable=True))
    op.add_column('api_keys', sa.Column('qps_limit', sa.Integer(), nullable=True, server_default='10'))
