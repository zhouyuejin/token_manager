"""api key rate limit fields

Revision ID: 20260915_1100_api_key_rate_limits
Revises: 20260915_1000_api_key_lifecycle
Create Date: 2026-09-15 11:00:00
"""
from alembic import op
import sqlalchemy as sa


revision = '20260915_1100_api_key_rate_limits'
down_revision = '20260915_1000_api_key_lifecycle'
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column('api_keys', sa.Column('qps_limit', sa.Integer(), nullable=False, server_default='0', comment='每秒请求限制，0表示不限制'))
    op.add_column('api_keys', sa.Column('rpm_limit', sa.Integer(), nullable=False, server_default='0', comment='每分钟请求限制，0表示不限制'))
    op.add_column('api_keys', sa.Column('tpm_limit', sa.Integer(), nullable=False, server_default='0', comment='每分钟估算Token限制，0表示不限制'))
    op.add_column('api_keys', sa.Column('concurrency_limit', sa.Integer(), nullable=False, server_default='0', comment='并发请求限制，0表示不限制'))


def downgrade() -> None:
    op.drop_column('api_keys', 'concurrency_limit')
    op.drop_column('api_keys', 'tpm_limit')
    op.drop_column('api_keys', 'rpm_limit')
    op.drop_column('api_keys', 'qps_limit')
