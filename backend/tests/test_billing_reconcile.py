from datetime import date, datetime, timedelta
from decimal import Decimal

from sqlalchemy import BigInteger, create_engine
from sqlalchemy.ext.compiler import compiles
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

import app.models  # noqa: F401
from app.core.database import Base
from app.models.billing_reconcile import BillingReconcileItem, BillingReconcileReport
from app.models.quota_reservation import QuotaReservation
from app.models.usage_log import UsageLog
from app.services.billing_reconcile_service import BillingReconcileService


@compiles(BigInteger, "sqlite")
def sqlite_bigint(element, compiler, **kw):
    return "INTEGER"


def make_db():
    engine = create_engine("sqlite://", connect_args={"check_same_thread": False}, poolclass=StaticPool)
    Base.metadata.create_all(engine)
    return sessionmaker(bind=engine)()


def reservation(reservation_id="reservation-1", status="committed", actual_tokens=100, actual_cost=Decimal("0.25000000")):
    created = datetime(2026, 9, 20, 8)
    return QuotaReservation(
        reservation_id=reservation_id, user_id="user-1", key_id="key-1", project_id="project-1",
        department_id="dept-1", model="gpt-test", estimated_tokens=120, actual_tokens=actual_tokens,
        estimated_cost_usd=Decimal("0.30000000"), actual_cost_usd=actual_cost, budget_accounted=True,
        price_type="token", input_price=Decimal("1"), output_price=Decimal("2"), request_price=Decimal("0"),
        status=status, created_at=created, updated_at=created, expires_at=created + timedelta(minutes=5),
    )


def usage(reservation_id="reservation-1", total_tokens=100, cost=Decimal("0.25000000")):
    return UsageLog(
        log_id=f"usage-{reservation_id}", user_id="user-1", key_id="key-1", channel_id="channel-1",
        model="gpt-test", project_id="project-1", department_id="dept-1", reservation_id=reservation_id,
        prompt_tokens=70, completion_tokens=30, total_tokens=total_tokens, cost_usd=cost,
        latency_ms=10, status_code=200, created_at=datetime(2026, 9, 20, 8, 1),
    )


def test_normal_report_and_idempotent_rerun():
    db = make_db()
    db.add_all([reservation(), usage()])
    db.commit()
    service = BillingReconcileService(db)
    report = service.run(date(2026, 9, 20), now=datetime(2026, 9, 21, 3))
    assert report.status == "normal"
    assert report.anomaly_count == 0
    report_id = report.report_id
    assert service.run(date(2026, 9, 20), now=datetime(2026, 9, 21, 4)).report_id == report_id
    assert db.query(BillingReconcileReport).count() == 1


def test_mismatch_and_stale_reservation_are_snapshotted():
    db = make_db()
    stale = reservation("stale", status="reserved", actual_tokens=None, actual_cost=None)
    stale.expires_at = datetime(2026, 9, 20, 8, 5)
    db.add_all([reservation(), usage(total_tokens=99), stale])
    db.commit()
    report = BillingReconcileService(db).run(date(2026, 9, 20), now=datetime(2026, 9, 21, 3))
    assert report.status == "abnormal"
    assert {row.anomaly_type for row in db.query(BillingReconcileItem).all()} == {
        "committed_usage_mismatch", "expired_lease_still_reserved"
    }


def test_missing_cost_and_reservation_are_reported_after_coverage_start():
    db = make_db()
    missing_cost = usage("missing-cost", cost=None)
    orphan = usage("orphan", cost=Decimal("0.10000000"))
    orphan.log_id = "orphan"
    db.add_all([missing_cost, orphan])
    db.commit()
    report = BillingReconcileService(db).run(date(2026, 9, 20), now=datetime(2026, 9, 21, 3))
    assert report.status == "abnormal"
    assert {row.anomaly_type for row in db.query(BillingReconcileItem).all()} == {
        "usage_missing_cost", "usage_missing_reservation"
    }
