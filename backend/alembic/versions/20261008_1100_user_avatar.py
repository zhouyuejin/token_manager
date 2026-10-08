"""Add optional user avatar."""
from alembic import op
import sqlalchemy as sa

revision = "20261008_1100_user_avatar"
down_revision = "20261008_1000_user_nickname"
branch_labels = None
depends_on = None


def upgrade():
    op.add_column("users", sa.Column("avatar_url", sa.Text(), nullable=True))


def downgrade():
    op.drop_column("users", "avatar_url")
