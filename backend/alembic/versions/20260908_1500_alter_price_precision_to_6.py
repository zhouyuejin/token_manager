"""widen price columns to DECIMAL(10, 6)

Revision ID: alter_price_precision_to_6
Revises: change_price_unit_to_usd
Create Date: 2026-09-08 15:00:00.000000

变更说明：
把 model_mappings 表上三列定价字段的数值精度从 DECIMAL(10, 4) 扩到
DECIMAL(10, 6)，让后续的 CNY → USD 换算（divide by 7.2）能保留更高
精度，避免小数值被舍入到 0。

只扩 scale 不动 precision，长度上限仍是 10 位有效数字。
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import mysql

# revision identifiers, used by Alembic.
revision: str = 'alter_price_precision_to_6'
down_revision: Union[str, None] = 'change_price_unit_to_usd'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.alter_column(
        'model_mappings', 'price_per_1k_input',
        existing_type=mysql.DECIMAL(precision=10, scale=4),
        type_=mysql.DECIMAL(precision=10, scale=6),
        existing_nullable=False,
        existing_server_default=sa.text("'0.0000'"),
    )
    op.alter_column(
        'model_mappings', 'price_per_1k_output',
        existing_type=mysql.DECIMAL(precision=10, scale=4),
        type_=mysql.DECIMAL(precision=10, scale=6),
        existing_nullable=False,
        existing_server_default=sa.text("'0.0000'"),
    )
    op.alter_column(
        'model_mappings', 'price_per_request',
        existing_type=mysql.DECIMAL(precision=10, scale=4),
        type_=mysql.DECIMAL(precision=10, scale=6),
        existing_nullable=False,
        existing_server_default=sa.text("'0.0000'"),
    )


def downgrade() -> None:
    # 注意：缩到 4 位会丢失已经被扩到 6 位的末两位。
    op.alter_column(
        'model_mappings', 'price_per_1k_input',
        existing_type=mysql.DECIMAL(precision=10, scale=6),
        type_=mysql.DECIMAL(precision=10, scale=4),
        existing_nullable=False,
        existing_server_default=sa.text("'0.000000'"),
    )
    op.alter_column(
        'model_mappings', 'price_per_1k_output',
        existing_type=mysql.DECIMAL(precision=10, scale=6),
        type_=mysql.DECIMAL(precision=10, scale=4),
        existing_nullable=False,
        existing_server_default=sa.text("'0.000000'"),
    )
    op.alter_column(
        'model_mappings', 'price_per_request',
        existing_type=mysql.DECIMAL(precision=10, scale=6),
        type_=mysql.DECIMAL(precision=10, scale=4),
        existing_nullable=False,
        existing_server_default=sa.text("'0.000000'"),
    )
