"""Add daily billing reconciliation reports and anomaly snapshots."""
from alembic import op
import sqlalchemy as sa

revision = "20260920_1200_billing_reconcile"
down_revision = "20260918_1200_budgets"
branch_labels = None
depends_on = None


def upgrade():
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    if not inspector.has_table("billing_reconcile_reports"):
        op.create_table(
            "billing_reconcile_reports",
            sa.Column("report_id", sa.String(32), primary_key=True),
            sa.Column("business_date", sa.Date(), nullable=False),
            sa.Column("status", sa.String(16), nullable=False),
            sa.Column("reservation_count", sa.Integer(), nullable=False, server_default="0"),
            sa.Column("usage_count", sa.Integer(), nullable=False, server_default="0"),
            sa.Column("quota_record_count", sa.Integer(), nullable=False, server_default="0"),
            sa.Column("anomaly_count", sa.Integer(), nullable=False, server_default="0"),
            sa.Column("started_at", sa.DateTime(), nullable=False),
            sa.Column("finished_at", sa.DateTime(), nullable=True),
            sa.Column("error_message", sa.Text(), nullable=True),
            sa.UniqueConstraint("business_date", name="uq_reconcile_report_business_date"),
        )
    if not inspector.has_table("billing_reconcile_items"):
        op.create_table(
            "billing_reconcile_items",
            sa.Column("item_id", sa.String(32), primary_key=True),
            sa.Column("report_id", sa.String(32), nullable=False),
            sa.Column("anomaly_type", sa.String(64), nullable=False),
            sa.Column("reservation_id", sa.String(32), nullable=True),
            sa.Column("usage_log_id", sa.BigInteger(), nullable=True),
            sa.Column("quota_record_id", sa.String(32), nullable=True),
            sa.Column("user_id", sa.String(32), nullable=True),
            sa.Column("expected_value", sa.Text(), nullable=True),
            sa.Column("actual_value", sa.Text(), nullable=True),
            sa.Column("detail", sa.Text(), nullable=False),
            sa.Column("created_at", sa.DateTime(), nullable=False),
            sa.UniqueConstraint("report_id", "anomaly_type", "reservation_id", "usage_log_id", "quota_record_id", name="uq_reconcile_item_source"),
        )
        op.create_index("ix_reconcile_items_report_id", "billing_reconcile_items", ["report_id"])
        op.create_index("ix_reconcile_items_anomaly_type", "billing_reconcile_items", ["anomaly_type"])
        op.create_index("ix_reconcile_items_reservation_id", "billing_reconcile_items", ["reservation_id"])
        op.create_index("ix_reconcile_items_usage_log_id", "billing_reconcile_items", ["usage_log_id"])
        op.create_index("ix_reconcile_items_quota_record_id", "billing_reconcile_items", ["quota_record_id"])
        op.create_index("ix_reconcile_items_report_type", "billing_reconcile_items", ["report_id", "anomaly_type"])


def downgrade():
    op.drop_table("billing_reconcile_items")
    op.drop_table("billing_reconcile_reports")
