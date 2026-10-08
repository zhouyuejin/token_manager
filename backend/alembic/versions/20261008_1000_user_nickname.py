"""Add optional user nicknames without changing login accounts."""
from alembic import op
import sqlalchemy as sa


revision = "20261008_1000_user_nickname"
down_revision = "20260929_1400_user_rate_limits"
branch_labels = None
depends_on = None


def upgrade():
    op.add_column("users", sa.Column("nickname", sa.String(50), nullable=True, comment="用户昵称"))


def downgrade():
    op.drop_column("users", "nickname")
