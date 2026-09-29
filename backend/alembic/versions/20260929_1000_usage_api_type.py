"""Add API type to usage logs."""
from alembic import op
import sqlalchemy as sa

revision = '20260929_1000_usage_api_type'
down_revision = '20260928_1500_approval_supplement'
branch_labels = None
depends_on = None


def upgrade():
    columns = {column['name'] for column in sa.inspect(op.get_bind()).get_columns('usage_logs')}
    if 'api_type' not in columns:
        op.add_column('usage_logs', sa.Column('api_type', sa.String(32), nullable=False, server_default='chat', comment='代理接口类型'))


def downgrade():
    columns = {column['name'] for column in sa.inspect(op.get_bind()).get_columns('usage_logs')}
    if 'api_type' in columns:
        op.drop_column('usage_logs', 'api_type')
