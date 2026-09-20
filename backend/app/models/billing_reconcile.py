"""Daily billing reconciliation snapshots."""
from sqlalchemy import BigInteger, Column, Date, DateTime, Index, Integer, String, Text, UniqueConstraint

from app.core.database import Base


class BillingReconcileReport(Base):
    __tablename__ = "billing_reconcile_reports"

    report_id = Column(String(32), primary_key=True)
    business_date = Column(Date, nullable=False, unique=True)
    status = Column(String(16), nullable=False)
    reservation_count = Column(Integer, nullable=False, default=0)
    usage_count = Column(Integer, nullable=False, default=0)
    quota_record_count = Column(Integer, nullable=False, default=0)
    anomaly_count = Column(Integer, nullable=False, default=0)
    started_at = Column(DateTime, nullable=False)
    finished_at = Column(DateTime, nullable=True)
    error_message = Column(Text, nullable=True)


class BillingReconcileItem(Base):
    __tablename__ = "billing_reconcile_items"

    item_id = Column(String(32), primary_key=True)
    report_id = Column(String(32), nullable=False, index=True)
    anomaly_type = Column(String(64), nullable=False, index=True)
    reservation_id = Column(String(32), nullable=True, index=True)
    usage_log_id = Column(BigInteger, nullable=True, index=True)
    quota_record_id = Column(String(32), nullable=True, index=True)
    user_id = Column(String(32), nullable=True)
    expected_value = Column(Text, nullable=True)
    actual_value = Column(Text, nullable=True)
    detail = Column(Text, nullable=False)
    created_at = Column(DateTime, nullable=False)

    __table_args__ = (
        UniqueConstraint(
            "report_id", "anomaly_type", "reservation_id", "usage_log_id", "quota_record_id",
            name="uq_reconcile_item_source",
        ),
        Index("ix_reconcile_items_report_type", "report_id", "anomaly_type"),
    )
