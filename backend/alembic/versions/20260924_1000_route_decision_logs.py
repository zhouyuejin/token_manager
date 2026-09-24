"""Add route decision logs."""
from alembic import op
import sqlalchemy as sa


revision = "20260924_1000_route_decision_logs"
down_revision = "20260920_1200_billing_reconcile"
branch_labels = None
depends_on = None


def upgrade():
    inspector = sa.inspect(op.get_bind())
    if not inspector.has_table("route_decision_logs"):
        op.create_table(
            "route_decision_logs",
            sa.Column("id", sa.BigInteger(), primary_key=True, autoincrement=True),
            sa.Column("request_id", sa.String(64), nullable=False),
            sa.Column("user_id", sa.String(32), nullable=True),
            sa.Column("key_id", sa.String(32), nullable=True),
            sa.Column("model", sa.String(100), nullable=False),
            sa.Column("candidate_channels", sa.Text(), nullable=False),
            sa.Column("skipped_reasons", sa.Text(), nullable=False),
            sa.Column("selected_channel", sa.String(32), nullable=True),
            sa.Column("retry_path", sa.Text(), nullable=False),
            sa.Column("status_code", sa.Integer(), nullable=False),
            sa.Column("success", sa.Boolean(), nullable=False),
            sa.Column("error_message", sa.Text(), nullable=True),
            sa.Column("created_at", sa.DateTime(), server_default=sa.func.now(), nullable=False),
        )
        inspector = sa.inspect(op.get_bind())
    existing_indexes = {index["name"] for index in inspector.get_indexes("route_decision_logs")}
    for name, column in (
        ("request_id", "request_id"), ("user_id", "user_id"),
        ("key_id", "key_id"), ("model", "model"),
        ("selected_channel", "selected_channel"), ("created_at", "created_at"),
    ):
        index_name = f"ix_route_decision_logs_{name}"
        if index_name not in existing_indexes:
            op.create_index(index_name, "route_decision_logs", [column])
    if "ix_route_decision_request_created" not in existing_indexes:
        op.create_index("ix_route_decision_request_created", "route_decision_logs", ["request_id", "created_at"])


def downgrade():
    op.drop_table("route_decision_logs")
