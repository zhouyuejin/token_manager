"""Add OIDC identity and role permissions."""
from alembic import op
import sqlalchemy as sa

revision = "20260929_1100_oidc_rbac"
down_revision = "20260929_1000_usage_api_type"
branch_labels = None
depends_on = None


def upgrade():
    inspector = sa.inspect(op.get_bind())
    columns = {column["name"] for column in inspector.get_columns("users")}
    if "oidc_subject" not in columns:
        op.add_column("users", sa.Column("oidc_subject", sa.String(255), nullable=True))
        op.create_index("ix_users_oidc_subject", "users", ["oidc_subject"], unique=True)
    elif not any(
        index.get("unique") and index.get("column_names") == ["oidc_subject"]
        for index in inspector.get_indexes("users")
    ) and not any(
        constraint.get("column_names") == ["oidc_subject"]
        for constraint in inspector.get_unique_constraints("users")
    ):
        op.create_index("ix_users_oidc_subject", "users", ["oidc_subject"], unique=True)

    op.execute("ALTER TABLE users MODIFY COLUMN role ENUM('admin','department_admin','auditor','user') NOT NULL DEFAULT 'user'")
    if not inspector.has_table("role_permissions"):
        op.create_table(
            "role_permissions",
            sa.Column("role", sa.String(32), primary_key=True),
            sa.Column("permission", sa.String(64), primary_key=True),
        )
    op.execute("""
        INSERT IGNORE INTO role_permissions (role, permission) VALUES
        ('admin', 'admin:read'), ('admin', 'admin:write'),
        ('department_admin', 'department:read'), ('department_admin', 'department:write'),
        ('auditor', 'admin:read')
    """)


def downgrade():
    op.execute("UPDATE users SET role='user' WHERE role IN ('department_admin','auditor')")
    op.execute("ALTER TABLE users MODIFY COLUMN role ENUM('admin','user') NOT NULL DEFAULT 'user'")
    op.drop_table("role_permissions")
    inspector = sa.inspect(op.get_bind())
    if "oidc_subject" in {column["name"] for column in inspector.get_columns("users")}:
        op.drop_index("ix_users_oidc_subject", table_name="users")
        op.drop_column("users", "oidc_subject")
