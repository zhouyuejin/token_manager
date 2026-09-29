"""Add aggregate rate limits to users."""
from alembic import op
import sqlalchemy as sa


revision = "20260929_1400_user_rate_limits"
down_revision = "20260929_1300_channel_advanced_defaults"
branch_labels = None
depends_on = None


def upgrade():
    for name, comment in (
        ("qps_limit", "用户每秒请求限制，0表示不限制"),
        ("rpm_limit", "用户每分钟请求限制，0表示不限制"),
        ("tpm_limit", "用户每分钟估算Token限制，0表示不限制"),
        ("concurrency_limit", "用户并发请求限制，0表示不限制"),
    ):
        op.add_column("users", sa.Column(
            name, sa.Integer(), nullable=False, server_default="0", comment=comment,
        ))


def downgrade():
    for name in ("concurrency_limit", "tpm_limit", "rpm_limit", "qps_limit"):
        op.drop_column("users", name)
