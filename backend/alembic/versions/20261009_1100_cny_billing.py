"""Add explicit CNY ledger and frozen FX fields; preserve original USD amounts.

Backfill using python -m app.scripts.migrate_cny_billing while API admission is stopped.
"""
from alembic import op
import sqlalchemy as sa

revision = '20261009_1100_cny_billing'
down_revision = '20261009_1000_department_chat'
branch_labels = None
depends_on = None


def upgrade():
    bind = op.get_bind()
    columns = {t: {c['name'] for c in sa.inspect(bind).get_columns(t)}
               for t in ('models', 'usage_logs', 'quota_reservations', 'budgets')}
    additions = {
        'models': [sa.Column('price_currency', sa.String(3), nullable=False, server_default='USD')],
        'usage_logs': [sa.Column('cost_cny', sa.Numeric(18, 8), nullable=True)],
        'quota_reservations': [sa.Column('estimated_cost_cny', sa.Numeric(18, 8), nullable=True),
                               sa.Column('actual_cost_cny', sa.Numeric(18, 8), nullable=True)],
        'budgets': [sa.Column('amount_cny', sa.Numeric(18, 8), nullable=True),
                    sa.Column('migration_exchange_rate', sa.Numeric(18, 8), nullable=True)],
    }
    for table in ('usage_logs', 'quota_reservations'):
        additions[table] += [sa.Column('price_currency', sa.String(3), nullable=True),
            sa.Column('exchange_rate', sa.Numeric(18, 8), nullable=True),
            sa.Column('exchange_rate_date', sa.DateTime(), nullable=True),
            sa.Column('exchange_rate_source', sa.String(32), nullable=True),
            sa.Column('conversion_kind', sa.String(40), nullable=True)]
    for table, fields in additions.items():
        for field in fields:
            if field.name not in columns[table]:
                op.add_column(table, field)
    # New CNY records must not be required to populate old USD audit columns.
    for table, field in [('quota_reservations', 'estimated_cost_usd'), ('budgets', 'amount_usd')]:
        op.alter_column(table, field, existing_type=sa.Numeric(18, 8), nullable=True)
    op.alter_column('models', 'price_currency', existing_type=sa.String(3), server_default='CNY')
    for table, fields in [('models', ('price_per_1k_input', 'price_per_1k_output', 'price_per_request')),
                          ('quota_reservations', ('input_price', 'output_price', 'request_price'))]:
        for field in fields:
            column = next(c for c in sa.inspect(bind).get_columns(table) if c['name'] == field)
            if column['type'].scale != 12:
                op.alter_column(table, field, existing_type=column['type'], type_=sa.Numeric(24, 12),
                                existing_nullable=False)



def downgrade():
    raise RuntimeError('人民币账本不能自动降级为美元；请恢复切换前备份。')
