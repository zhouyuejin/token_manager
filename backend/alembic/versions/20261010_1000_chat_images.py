"""Allow chat messages to persist inline image data."""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import mysql

revision = '20261010_1000_chat_images'
down_revision = '20261009_1100_cny_billing'
branch_labels = None
depends_on = None


def upgrade():
    op.alter_column('chat_messages', 'content', existing_type=sa.Text(),
                    type_=mysql.LONGTEXT(), existing_nullable=False)


def downgrade():
    op.alter_column('chat_messages', 'content', existing_type=mysql.LONGTEXT(),
                    type_=sa.Text(), existing_nullable=False)
