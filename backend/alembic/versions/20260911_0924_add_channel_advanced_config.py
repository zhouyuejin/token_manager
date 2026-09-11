"""
add_channel_advanced_config

为 channels 表添加上游格式与认证方式的高级配置字段。

Revision ID: 20260911_0924_add_channel_advanced_config
Revises: 20260910_channels_models_refactor
Create Date: 2026-09-11 09:24:00
"""
from alembic import op
import sqlalchemy as sa

revision = '20260911_0924_add_channel_advanced_config'
down_revision = '20260910_channels_models_refactor'
branch_labels = None
depends_on = None


def upgrade() -> None:
    """添加高级配置字段，全部带默认值保证存量数据兼容"""
    op.add_column(
        'channels',
        sa.Column(
            'upstream_format',
            sa.String(32),
            nullable=False,
            server_default='chat',
            comment='上游API格式: chat/anthropic/gemini/responses/auto'
        )
    )
    op.add_column(
        'channels',
        sa.Column(
            'auth_type',
            sa.String(32),
            nullable=False,
            server_default='auto',
            comment='认证方式: auto/bearer/api_key/azure_api_key/query_key'
        )
    )
    op.add_column(
        'channels',
        sa.Column(
            'auth_headers',
            sa.Text(),
            nullable=True,
            comment='自定义认证Header配置JSON'
        )
    )


def downgrade() -> None:
    op.drop_column('channels', 'auth_headers')
    op.drop_column('channels', 'auth_type')
    op.drop_column('channels', 'upstream_format')
