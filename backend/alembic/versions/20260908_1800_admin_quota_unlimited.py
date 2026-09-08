"""set admin user quota to unlimited sentinel

Revision ID: admin_quota_unlimited
Revises: add_user_registered_enum
Create Date: 2026-09-08 18:00:00.000000

变更说明：
配合 ProxyService 的 admin 短路逻辑（admin → effective unlimited），
把存量 username='admin' 的用户 quota 从 100000000（init 时的初始值）
改为 -1（unlimited sentinel）。

幂等：WHERE 条件过滤掉已经是 -1 的行，重复执行 no-op。

downgrade：把 username='admin' 的 quota 改回 100000000。
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'admin_quota_unlimited'
down_revision: Union[str, None] = 'add_user_registered_enum'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


ADMIN_INITIAL_QUOTA = 100000000


def upgrade() -> None:
    """把 username='admin' 且 quota != -1 的行改为 unlimited sentinel -1。"""
    op.execute(
        "UPDATE users SET quota = -1 "
        "WHERE username = 'admin' AND quota <> -1"
    )


def downgrade() -> None:
    """回滚：把 username='admin' 的 quota 改回 100000000。
    注意：仅在「升级后立刻回滚」才精确；任何升级后的手工修改都会被覆盖。"""
    op.execute(
        "UPDATE users SET quota = " f"{ADMIN_INITIAL_QUOTA} "
        "WHERE username = 'admin'"
    )
