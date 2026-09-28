"""add approval requests"""
from alembic import op
import sqlalchemy as sa

revision = '20260928_1300_approval_requests'
down_revision = '20260928_1200_alert_rules'
branch_labels = None
depends_on = None


def upgrade():
    if 'approval_requests' in sa.inspect(op.get_bind()).get_table_names():
        return
    op.create_table(
        'approval_requests',
        sa.Column('request_id', sa.String(32), primary_key=True),
        sa.Column('request_type', sa.String(32), nullable=False),
        sa.Column('requester_user_id', sa.String(32), nullable=False),
        sa.Column('approver_user_id', sa.String(32), nullable=True),
        sa.Column('target_id', sa.String(32), nullable=True),
        sa.Column('payload', sa.JSON(), nullable=False),
        sa.Column('status', sa.String(16), nullable=False, server_default='pending'),
        sa.Column('reason', sa.Text(), nullable=False),
        sa.Column('decision_comment', sa.Text(), nullable=True),
        sa.Column('created_at', sa.DateTime(), nullable=False, server_default=sa.func.now()),
        sa.Column('decided_at', sa.DateTime(), nullable=True),
    )
    op.create_index('ix_approval_requests_request_type', 'approval_requests', ['request_type'])
    op.create_index('ix_approval_requests_requester_user_id', 'approval_requests', ['requester_user_id'])
    op.create_index('ix_approval_requests_approver_user_id', 'approval_requests', ['approver_user_id'])
    op.create_index('ix_approval_requests_status', 'approval_requests', ['status'])


def downgrade():
    if 'approval_requests' not in sa.inspect(op.get_bind()).get_table_names():
        return
    op.drop_index('ix_approval_requests_status', table_name='approval_requests')
    op.drop_index('ix_approval_requests_approver_user_id', table_name='approval_requests')
    op.drop_index('ix_approval_requests_requester_user_id', table_name='approval_requests')
    op.drop_index('ix_approval_requests_request_type', table_name='approval_requests')
    op.drop_table('approval_requests')
