"""请求额度预扣及结算记录。"""
from alembic import op
import sqlalchemy as sa

revision = '20260917_1100_quota_reservations'
down_revision = '20260917_1000_project_attribution'
branch_labels = None
depends_on = None


def upgrade():
    # main.py create_all 可能已预建表。
    if sa.inspect(op.get_bind()).has_table('quota_reservations'):
        return
    op.create_table('quota_reservations',
        sa.Column('reservation_id', sa.String(32), primary_key=True),
        sa.Column('user_id', sa.String(32), nullable=False),
        sa.Column('key_id', sa.String(32), nullable=False),
        sa.Column('project_id', sa.String(32)),
        sa.Column('department_id', sa.String(32)),
        sa.Column('model', sa.String(50), nullable=False),
        sa.Column('estimated_tokens', sa.BigInteger(), nullable=False),
        sa.Column('actual_tokens', sa.BigInteger()),
        sa.Column('estimated_cost_usd', sa.Numeric(18, 8), nullable=False),
        sa.Column('actual_cost_usd', sa.Numeric(18, 8)),
        sa.Column('price_type', sa.String(16), nullable=False),
        sa.Column('input_price', sa.Numeric(10, 6), nullable=False),
        sa.Column('output_price', sa.Numeric(10, 6), nullable=False),
        sa.Column('request_price', sa.Numeric(10, 6), nullable=False),
        sa.Column('status', sa.String(16), nullable=False),
        sa.Column('created_at', sa.DateTime(), nullable=False),
        sa.Column('updated_at', sa.DateTime(), nullable=False),
        sa.Column('expires_at', sa.DateTime(), nullable=False))
    op.create_index('ix_quota_reservations_user_id', 'quota_reservations', ['user_id'])
    op.create_index('ix_quota_reservations_key_id', 'quota_reservations', ['key_id'])
    op.create_index('ix_reservation_expiry', 'quota_reservations', ['status', 'expires_at'])


def downgrade():
    op.drop_table('quota_reservations')
