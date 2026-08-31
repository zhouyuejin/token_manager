"""add_chat_tables

Revision ID: 001_add_chat_tables
Revises: 
Create Date: 2024-08-31

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '001_add_chat_tables'
down_revision: Union[str, None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # 创建 chat_conversations 表
    op.create_table(
        'chat_conversations',
        sa.Column('id', sa.BigInteger(), autoincrement=True, nullable=False),
        sa.Column('conversation_id', sa.String(32), nullable=False),
        sa.Column('user_id', sa.String(32), nullable=False),
        sa.Column('title', sa.String(255), nullable=True),
        sa.Column('provider_id', sa.String(32), nullable=True),
        sa.Column('model_id', sa.String(32), nullable=True),
        sa.Column('system_prompt', sa.Text(), nullable=True),
        sa.Column('created_at', sa.DateTime(), server_default=sa.text('CURRENT_TIMESTAMP'), nullable=True),
        sa.Column('updated_at', sa.DateTime(), server_default=sa.text('CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP'), nullable=True),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('conversation_id')
    )
    op.create_index('idx_conversation_user_id', 'chat_conversations', ['user_id'])
    op.create_index('idx_conversation_user_created', 'chat_conversations', ['user_id', 'created_at'])
    
    # 创建 chat_messages 表
    op.create_table(
        'chat_messages',
        sa.Column('id', sa.BigInteger(), autoincrement=True, nullable=False),
        sa.Column('message_id', sa.String(32), nullable=False),
        sa.Column('conversation_id', sa.String(32), nullable=False),
        sa.Column('role', sa.String(20), nullable=False),
        sa.Column('content', sa.Text(), nullable=False),
        sa.Column('model', sa.String(50), nullable=True),
        sa.Column('tokens', sa.Integer(), nullable=True),
        sa.Column('created_at', sa.DateTime(), server_default=sa.text('CURRENT_TIMESTAMP'), nullable=True),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('message_id'),
        sa.ForeignKeyConstraint(['conversation_id'], ['chat_conversations.conversation_id'], ondelete='CASCADE')
    )
    op.create_index('idx_message_conversation_id', 'chat_messages', ['conversation_id'])
    op.create_index('idx_message_conversation_created', 'chat_messages', ['conversation_id', 'created_at'])


def downgrade() -> None:
    op.drop_index('idx_message_conversation_created', table_name='chat_messages')
    op.drop_index('idx_message_conversation_id', table_name='chat_messages')
    op.drop_table('chat_messages')
    op.drop_index('idx_conversation_user_created', table_name='chat_conversations')
    op.drop_index('idx_conversation_user_id', table_name='chat_conversations')
    op.drop_table('chat_conversations')
