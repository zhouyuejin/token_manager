"""Track mail delivery; do not mail historical notifications."""
from alembic import op
import sqlalchemy as sa

revision = '20261010_1100_notification_email'
down_revision = '20261010_1000_chat_images'
branch_labels = None
depends_on = None


def upgrade():
    op.add_column('notifications', sa.Column('email_status', sa.String(16), nullable=False, server_default='skipped'))
    op.add_column('notifications', sa.Column('email_attempts', sa.Integer(), nullable=False, server_default='0'))
    op.alter_column('notifications', 'email_status', server_default='pending', existing_type=sa.String(16), existing_nullable=False)
    op.create_index('idx_notification_email', 'notifications', ['email_status', 'id'])


def downgrade():
    op.drop_index('idx_notification_email', table_name='notifications')
    op.drop_column('notifications', 'email_attempts')
    op.drop_column('notifications', 'email_status')
