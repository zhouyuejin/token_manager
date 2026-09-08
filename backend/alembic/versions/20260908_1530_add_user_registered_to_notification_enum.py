"""add user_registered to notifications.type enum

Revision ID: add_user_registered_enum
Revises: convert_price_cny_to_usd
Create Date: 2026-09-08 15:30:00.000000

背景：Python 端 NotificationType 枚举新增了 user_registered，但
notifications.type 列的 MySQL ENUM 没同步扩展，导致向管理员发新用户
注册通知时 SQL 报 (1265, "Data truncated for column 'type' at row 1")，
并连带把调用方的 SQLAlchemy session 毒化，最终 500。
"""
from typing import Sequence, Union

from alembic import op


# revision identifiers, used by Alembic.
revision: str = 'add_user_registered_enum'
down_revision: Union[str, None] = 'convert_price_cny_to_usd'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.execute(
        "ALTER TABLE notifications "
        "MODIFY COLUMN type "
        "ENUM('quota_low','quota_increase','quota_decrease','daily_report','system','user_registered') "
        "NOT NULL"
    )


def downgrade() -> None:
    # 回滚前需要先清掉所有 user_registered 类型的记录，否则 ALTER 会失败
    op.execute(
        "ALTER TABLE notifications "
        "MODIFY COLUMN type "
        "ENUM('quota_low','quota_increase','quota_decrease','daily_report','system') "
        "NOT NULL"
    )
