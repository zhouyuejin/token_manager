"""部门、项目授权及用量归因；历史日志不回填。"""
from alembic import op
import sqlalchemy as sa

revision = '20260917_1000_project_attribution'
down_revision = '20260915_1200_api_key_freeze'
branch_labels = None
depends_on = None


def upgrade():
    if not sa.inspect(op.get_bind()).has_table('departments'):
        op.create_table('departments',
            sa.Column('dept_id', sa.String(32), primary_key=True),
            sa.Column('name', sa.String(100), nullable=False),
            sa.Column('owner_user_id', sa.String(32), nullable=True),
            sa.Column('status', sa.String(16), nullable=False))
    if not sa.inspect(op.get_bind()).has_table('projects'):
        op.create_table('projects',
            sa.Column('project_id', sa.String(32), primary_key=True),
            sa.Column('dept_id', sa.String(32), sa.ForeignKey('departments.dept_id'), nullable=False),
            sa.Column('name', sa.String(100), nullable=False),
            sa.Column('owner_user_id', sa.String(32), nullable=True),
            sa.Column('status', sa.String(16), nullable=False))
        op.create_index('ix_projects_dept_id', 'projects', ['dept_id'])
    if not sa.inspect(op.get_bind()).has_table('user_projects'):
        op.create_table('user_projects',
            sa.Column('user_id', sa.String(32), sa.ForeignKey('users.user_id', ondelete='CASCADE'), primary_key=True),
            sa.Column('project_id', sa.String(32), sa.ForeignKey('projects.project_id', ondelete='CASCADE'), primary_key=True))
    op.add_column('api_keys', sa.Column('project_id', sa.String(32), nullable=True))
    op.create_index('ix_api_keys_project_id', 'api_keys', ['project_id'])
    for field in ('project_id', 'department_id'):
        op.add_column('usage_logs', sa.Column(field, sa.String(32), nullable=True))
        op.create_index('ix_usage_logs_' + field, 'usage_logs', [field])
    op.add_column('usage_logs', sa.Column('cost_usd', sa.Numeric(18, 8), nullable=True))
    op.execute("INSERT INTO departments (dept_id, name, status) VALUES ('dept_default', '默认部门', 'active')")
    op.execute("INSERT INTO projects (project_id, dept_id, name, status) VALUES ('project_default', 'dept_default', '默认项目', 'active')")
    op.execute("INSERT INTO user_projects (user_id, project_id) SELECT DISTINCT k.user_id, 'project_default' FROM api_keys k JOIN users u ON u.user_id = k.user_id")
    op.execute("UPDATE api_keys SET project_id = 'project_default'")


def downgrade():
    op.drop_column('usage_logs', 'cost_usd')
    for field in ('department_id', 'project_id'):
        op.drop_index('ix_usage_logs_' + field, table_name='usage_logs')
        op.drop_column('usage_logs', field)
    op.drop_index('ix_api_keys_project_id', table_name='api_keys')
    op.drop_column('api_keys', 'project_id')
    op.drop_table('user_projects')
    op.drop_index('ix_projects_dept_id', table_name='projects')
    op.drop_table('projects')
    op.drop_table('departments')
