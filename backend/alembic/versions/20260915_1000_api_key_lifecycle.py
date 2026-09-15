"""api key lifecycle fields

Revision ID: 20260915_1000_api_key_lifecycle
Revises: 20260914_1100_extend_channel_quota_windows
Create Date: 2026-09-15 10:00:00
"""
from alembic import op
import sqlalchemy as sa


revision = '20260915_1000_api_key_lifecycle'
down_revision = '20260914_1100_extend_channel_quota_windows'
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute(
        "ALTER TABLE api_keys "
        "MODIFY COLUMN status ENUM('active','disabled','revoked') NOT NULL DEFAULT 'active'"
    )
    op.add_column('api_keys', sa.Column('expires_at', sa.DateTime(), nullable=True, comment='过期时间'))
    op.add_column('api_keys', sa.Column('revoked_at', sa.DateTime(), nullable=True, comment='吊销时间'))
    op.add_column('api_keys', sa.Column('revoked_reason', sa.String(length=255), nullable=True, comment='吊销原因'))
    op.add_column('api_keys', sa.Column('last_used_ip', sa.String(length=64), nullable=True, comment='最后使用IP'))
    op.add_column('api_keys', sa.Column('last_used_user_agent', sa.String(length=500), nullable=True, comment='最后使用User-Agent'))


def downgrade() -> None:
    op.drop_column('api_keys', 'last_used_user_agent')
    op.drop_column('api_keys', 'last_used_ip')
    op.drop_column('api_keys', 'revoked_reason')
    op.drop_column('api_keys', 'revoked_at')
    op.drop_column('api_keys', 'expires_at')
    op.execute("UPDATE api_keys SET status='disabled' WHERE status='revoked'")
    op.execute(
        "ALTER TABLE api_keys "
        "MODIFY COLUMN status ENUM('active','disabled') NOT NULL DEFAULT 'active'"
    )
