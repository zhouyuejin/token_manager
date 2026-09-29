"""Add project content audit controls and redacted usage summaries."""
from alembic import op
import sqlalchemy as sa


revision = "20260929_1200_content_privacy"
down_revision = "20260929_1100_oidc_rbac"
branch_labels = None
depends_on = None


def upgrade():
    inspector = sa.inspect(op.get_bind())
    project_columns = {column["name"] for column in inspector.get_columns("projects")}
    if "content_audit_enabled" not in project_columns:
        op.add_column(
            "projects",
            sa.Column("content_audit_enabled", sa.Boolean(), nullable=False, server_default=sa.text("0")),
        )

    usage_columns = {column["name"] for column in inspector.get_columns("usage_logs")}
    if "request_summary" not in usage_columns:
        op.add_column("usage_logs", sa.Column("request_summary", sa.Text(), nullable=True))
    if "response_summary" not in usage_columns:
        op.add_column("usage_logs", sa.Column("response_summary", sa.Text(), nullable=True))


def downgrade():
    inspector = sa.inspect(op.get_bind())
    usage_columns = {column["name"] for column in inspector.get_columns("usage_logs")}
    if "response_summary" in usage_columns:
        op.drop_column("usage_logs", "response_summary")
    if "request_summary" in usage_columns:
        op.drop_column("usage_logs", "request_summary")
    project_columns = {column["name"] for column in inspector.get_columns("projects")}
    if "content_audit_enabled" in project_columns:
        op.drop_column("projects", "content_audit_enabled")
