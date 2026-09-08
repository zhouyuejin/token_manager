"""convert model mapping prices from CNY to USD

Revision ID: convert_price_cny_to_usd
Revises: change_price_unit_to_usd
Create Date: 2026-09-08 15:00:00.000000

变更说明：
按汇率 1 USD = 7.2 CNY，将 model_mappings 表中三列已存的价格数值换算成 USD。
0 值不受影响（0 / 7.2 = 0）。结果用 ROUND(..., 6) 显式保留 6 位小数。

注意：本迁移的换算精度依赖上一迁移 alter_price_precision_to_6 已把列扩到 DECIMAL(10, 6)；
换算结果保留到 6 位小数（ROUND(..., 6)）。如果原值过小
（如 < 0.0002 CNY），换算后会被舍入到 0。强烈建议在升级前先
SELECT * 备份原始价格：

    SELECT model_id, price_per_1k_input, price_per_1k_output, price_per_request
    FROM model_mappings
    WHERE price_per_1k_input <> 0
       OR price_per_1k_output <> 0
       OR price_per_request <> 0;

downgrade() 通过乘以 7.2 还原，但**仅在「升级后立刻回滚」才精确**。
任何在升级之后新录入的 USD 价格都会被错误地乘 7.2。请谨慎使用 downgrade。
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision: str = 'convert_price_cny_to_usd'
down_revision: Union[str, None] = 'alter_price_precision_to_6'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

CNY_PER_USD = 7.2


def upgrade() -> None:
    op.execute(
        "UPDATE model_mappings "
        f"SET price_per_1k_input  = ROUND(price_per_1k_input  / {CNY_PER_USD}, 6)"
    )
    op.execute(
        "UPDATE model_mappings "
        f"SET price_per_1k_output = ROUND(price_per_1k_output / {CNY_PER_USD}, 6)"
    )
    op.execute(
        "UPDATE model_mappings "
        f"SET price_per_request    = ROUND(price_per_request    / {CNY_PER_USD}, 6)"
    )


def downgrade() -> None:
    op.execute(
        "UPDATE model_mappings "
        f"SET price_per_1k_input  = ROUND(price_per_1k_input  * {CNY_PER_USD}, 6)"
    )
    op.execute(
        "UPDATE model_mappings "
        f"SET price_per_1k_output = ROUND(price_per_1k_output * {CNY_PER_USD}, 6)"
    )
    op.execute(
        "UPDATE model_mappings "
        f"SET price_per_request    = ROUND(price_per_request    * {CNY_PER_USD}, 6)"
    )
