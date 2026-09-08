"""change price unit comment to USD

Revision ID: change_price_unit_to_usd
Revises: 20260907_model_group_model_binding
Create Date: 2026-09-08 14:00:00.000000

变更说明：
将 model_mappings 表上三列定价字段的列注释从「单位:元」改为「单位:$」。
这一改动只更新列文档（comment），**不会**改写已存在的数值。

注意：如果此前管理员按「元」录入过价格，运行本迁移后这些数值仍会被原样保留，
但解释口径已变为 USD。运营方需要复核已配置的价格，必要时按 USD 重新录入。
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import mysql

# revision identifiers, used by Alembic.
revision: str = 'change_price_unit_to_usd'
down_revision: Union[str, None] = '20260907_mgmb'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.alter_column(
        'model_mappings', 'price_per_1k_input',
        existing_type=mysql.DECIMAL(precision=10, scale=4),
        comment='每千输入token价格(单位:$)',
        existing_comment='每千输入token价格(单位:元)',
        existing_nullable=False,
        existing_server_default=sa.text("'0.0000'"),
    )
    op.alter_column(
        'model_mappings', 'price_per_1k_output',
        existing_type=mysql.DECIMAL(precision=10, scale=4),
        comment='每千输出token价格(单位:$)',
        existing_comment='每千输出token价格(单位:元)',
        existing_nullable=False,
        existing_server_default=sa.text("'0.0000'"),
    )
    op.alter_column(
        'model_mappings', 'price_per_request',
        existing_type=mysql.DECIMAL(precision=10, scale=4),
        comment='每次请求价格(单位:$)',
        existing_comment='每次请求价格(单位:元)',
        existing_nullable=False,
        existing_server_default=sa.text("'0.0000'"),
    )


def downgrade() -> None:
    op.alter_column(
        'model_mappings', 'price_per_1k_input',
        existing_type=mysql.DECIMAL(precision=10, scale=4),
        comment='每千输入token价格(单位:元)',
        existing_comment='每千输入token价格(单位:$)',
        existing_nullable=False,
        existing_server_default=sa.text("'0.0000'"),
    )
    op.alter_column(
        'model_mappings', 'price_per_1k_output',
        existing_type=mysql.DECIMAL(precision=10, scale=4),
        comment='每千输出token价格(单位:元)',
        existing_comment='每千输出token价格(单位:$)',
        existing_nullable=False,
        existing_server_default=sa.text("'0.0000'"),
    )
    op.alter_column(
        'model_mappings', 'price_per_request',
        existing_type=mysql.DECIMAL(precision=10, scale=4),
        comment='每次请求价格(单位:元)',
        existing_comment='每次请求价格(单位:$)',
        existing_nullable=False,
        existing_server_default=sa.text("'0.0000'"),
    )
