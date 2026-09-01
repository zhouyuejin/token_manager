"""add notifications table

Revision ID: add_notifications
Revises: c511ac1c9d5f
Create Date: 2026-09-01

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import mysql

# revision identifiers, used by Alembic.
revision: str = 'add_notifications'
down_revision: Union[str, None] = 'c511ac1c9d5f'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        'notifications',
        sa.Column('id', sa.BigInteger(), autoincrement=True, nullable=False),
        sa.Column('notif_id', sa.String(32), nullable=False),
        sa.Column('user_id', sa.String(32), nullable=False),
        sa.Column('type', sa.Enum('quota_low', 'quota_increase', 'quota_decrease', 'daily_report', 'system', name='notificationtype'), nullable=False),
        sa.Column('title', sa.String(100), nullable=False),
        sa.Column('content', sa.Text(), nullable=True),
        sa.Column('is_read', sa.BigInteger(), server_default=sa.text("'0'"), nullable=False),
        sa.Column('extra_data', sa.Text(), nullable=True),
        sa.Column('created_at', sa.DateTime(), server_default=sa.text('CURRENT_TIMESTAMP'), nullable=True),
        sa.Column('read_at', sa.DateTime(), nullable=True),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('notif_id')
    )
    op.create_index('idx_user_unread', 'notifications', ['user_id', 'is_read'])
    op.create_index('idx_user_created', 'notifications', ['user_id', 'created_at'])


def downgrade() -> None:
    op.drop_index('idx_user_created', table_name='notifications')
    op.drop_index('idx_user_unread', table_name='notifications')
    op.drop_table('notifications')
