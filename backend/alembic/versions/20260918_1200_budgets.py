"""项目/部门月预算、告警去重及用量预扣关联。"""
from alembic import op
import sqlalchemy as sa

revision = '20260918_1200_budgets'
down_revision = '20260917_1100_quota_reservations'
branch_labels = None
depends_on = None


def upgrade():
    bind = op.get_bind()
    if 'budget_accounted' not in {c['name'] for c in sa.inspect(bind).get_columns('quota_reservations')}:
        op.add_column('quota_reservations', sa.Column('budget_accounted', sa.Boolean(), nullable=False, server_default=sa.false()))
    if not sa.inspect(bind).has_table('budgets'):
        op.create_table('budgets',
            sa.Column('budget_id', sa.String(32), primary_key=True),
            sa.Column('scope_type', sa.String(16), nullable=False),
            sa.Column('scope_id', sa.String(32), nullable=False),
            sa.Column('month', sa.String(7), nullable=False),
            sa.Column('amount_usd', sa.Numeric(18, 8), nullable=False),
            sa.Column('thresholds', sa.JSON(), nullable=False),
            sa.Column('policy', sa.String(16), nullable=False),
            sa.Column('enabled', sa.Boolean(), nullable=False),
            sa.UniqueConstraint('scope_type', 'scope_id', 'month', name='uq_budget_scope_month'))
    if not sa.inspect(bind).has_table('budget_alerts'):
        op.create_table('budget_alerts',
            sa.Column('alert_id', sa.String(32), primary_key=True),
            sa.Column('budget_id', sa.String(32), nullable=False),
            sa.Column('threshold', sa.Integer(), nullable=False),
            sa.UniqueConstraint('budget_id', 'threshold', name='uq_budget_alert_threshold'))
    if 'reservation_id' not in {c['name'] for c in sa.inspect(bind).get_columns('usage_logs')}:
        op.add_column('usage_logs', sa.Column('reservation_id', sa.String(32), nullable=True))
    if 'ix_usage_logs_reservation_id' not in {idx['name'] for idx in sa.inspect(bind).get_indexes('usage_logs')}:
        op.create_index('ix_usage_logs_reservation_id', 'usage_logs', ['reservation_id'])
    for table, prefix in [('quota_reservations', 'reservation'), ('usage_logs', 'usage')]:
        indexes = {idx['name'] for idx in sa.inspect(bind).get_indexes(table)}
        for kind in ['project', 'department']:
            name = f'ix_{prefix}_{kind}_month'
            if name not in indexes:
                op.create_index(name, table, [f'{kind}_id', 'created_at'])


def downgrade():
    inspector = sa.inspect(op.get_bind())
    for table, prefix in [('quota_reservations', 'reservation'), ('usage_logs', 'usage')]:
        names = {idx['name'] for idx in inspector.get_indexes(table)}
        for kind in ['project', 'department']:
            name = f'ix_{prefix}_{kind}_month'
            if name in names:
                op.drop_index(name, table_name=table)
    indexes = [idx for idx in inspector.get_indexes('usage_logs') if 'reservation_id' in idx['column_names']]
    # SQLite batch 重建表需要显式移除相关索引。
    with op.batch_alter_table('usage_logs') as batch:
        for idx in indexes:
            batch.drop_index(idx['name'])
        batch.drop_column('reservation_id')
    with op.batch_alter_table('quota_reservations') as batch:
        batch.drop_column('budget_accounted')
    op.drop_table('budget_alerts')
    op.drop_table('budgets')
