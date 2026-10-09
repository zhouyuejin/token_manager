"""Allow authenticated web chat to account directly to a user's department."""
from alembic import op
import sqlalchemy as sa

revision = '20261009_1000_department_chat'
down_revision = '20261008_1200_unprefix_imported_model_ids'
branch_labels = None
depends_on = None


def upgrade():
    inspector = sa.inspect(op.get_bind())
    if 'department_id' not in {c['name'] for c in inspector.get_columns('users')}:
        op.add_column('users', sa.Column('department_id', sa.String(32), nullable=True))
        op.create_index('ix_users_department_id', 'users', ['department_id'])
        op.create_foreign_key('fk_users_department_id', 'users', 'departments', ['department_id'], ['dept_id'])
    if 'content_audit_enabled' not in {c['name'] for c in inspector.get_columns('departments')}:
        op.add_column('departments', sa.Column('content_audit_enabled', sa.Boolean(), nullable=False, server_default=sa.text('0')))
    for table in ('usage_logs', 'quota_reservations'):
        op.alter_column(table, 'key_id', existing_type=sa.String(32), nullable=True)


def downgrade():
    bind = op.get_bind()
    for table in ('usage_logs', 'quota_reservations'):
        if bind.execute(sa.text(f'SELECT 1 FROM {table} WHERE key_id IS NULL LIMIT 1')).first():
            raise RuntimeError('已有无 Key 的网页对话账目，不能降级为 Key 必填；请保留现有账目')
    for table in ('usage_logs', 'quota_reservations'):
        op.alter_column(table, 'key_id', existing_type=sa.String(32), nullable=False)
    op.drop_column('departments', 'content_audit_enabled')
    inspector = sa.inspect(bind)
    for constraint in inspector.get_foreign_keys('users'):
        if constraint['constrained_columns'] == ['department_id']:
            op.drop_constraint(constraint['name'], 'users', type_='foreignkey')
    op.drop_index('ix_users_department_id', table_name='users')
    op.drop_column('users', 'department_id')
