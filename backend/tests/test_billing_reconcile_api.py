from datetime import date, datetime

from fastapi import FastAPI
from fastapi.testclient import TestClient
from sqlalchemy import BigInteger, create_engine
from sqlalchemy.ext.compiler import compiles
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

import app.models  # noqa: F401
from app.api.v1 import admin, billing
from app.core.database import Base, get_db
from app.dependencies import require_admin
from app.models.billing_reconcile import BillingReconcileItem, BillingReconcileReport
from app.models.quota_record import QuotaRecord, QuotaRecordType
from app.models.quota_reservation import QuotaReservation
from app.models.usage_log import UsageLog
from app.models.user import User, UserRole


@compiles(BigInteger, "sqlite")
def sqlite_bigint(element, compiler, **kw):
    return "INTEGER"


def test_report_list_and_filtered_items_contract():
    engine = create_engine("sqlite://", connect_args={"check_same_thread": False}, poolclass=StaticPool)
    Base.metadata.create_all(engine)
    db = sessionmaker(bind=engine)()
    report = BillingReconcileReport(
        report_id="report-1", business_date=date(2026, 9, 19), status="abnormal",
        reservation_count=1, usage_count=1, quota_record_count=0, anomaly_count=1,
        started_at=datetime(2026, 9, 20, 2), finished_at=datetime(2026, 9, 20, 2, 1),
    )
    db.add_all([report, BillingReconcileItem(
        item_id="item-1", report_id="report-1", anomaly_type="usage_missing_cost",
        usage_log_id=7, user_id="user-1", detail="missing", created_at=datetime(2026, 9, 20, 2),
    )])
    db.commit()
    app = FastAPI()
    app.include_router(billing.router, prefix="/admin/billing")
    app.dependency_overrides[get_db] = lambda: db
    app.dependency_overrides[require_admin] = lambda: object()
    client = TestClient(app)

    response = client.get("/admin/billing/reconcile/reports")
    assert response.status_code == 200
    assert response.json()["items"][0]["status"] == "abnormal"
    assert response.json()["timezone"] == "Asia/Shanghai"
    items = client.get("/admin/billing/reconcile/reports/report-1/items", params={"anomaly_type": "usage_missing_cost"})
    assert items.status_code == 200
    assert items.json()["items"][0]["usage_log_id"] == 7
    assert client.get("/admin/billing/reconcile/reports/missing/items").status_code == 404
    db.close()
    engine.dispose()


def test_quota_adjustment_writes_ledger_in_same_commit():
    engine = create_engine("sqlite://", connect_args={"check_same_thread": False}, poolclass=StaticPool)
    Base.metadata.create_all(engine)
    db = sessionmaker(bind=engine)()
    administrator = User(user_id="admin", username="admin", email="admin@test", password="hash", role=UserRole.admin)
    target = User(user_id="user-1", username="user", email="user@test", password="hash", quota=100)
    db.add_all([administrator, target])
    db.commit()
    app = FastAPI()
    app.include_router(admin.router, prefix="/admin")
    app.dependency_overrides[get_db] = lambda: db
    app.dependency_overrides[require_admin] = lambda: administrator
    response = TestClient(app).post("/admin/users/user-1/quota", json={"amount": 250, "reason": "budget"})
    assert response.status_code == 200, response.text
    row = db.query(QuotaRecord).one()
    assert (row.balance_before, row.balance_after, row.amount, row.type.value) == (100, 250, 150, "increase")
    db.close()
    engine.dispose()


def test_reconcile_items_include_linked_source_ledger_details():
    engine = create_engine("sqlite://", connect_args={"check_same_thread": False}, poolclass=StaticPool)
    Base.metadata.create_all(engine)
    db = sessionmaker(bind=engine)()
    created_at = datetime(2026, 9, 20, 2)
    report = BillingReconcileReport(
        report_id="report-details", business_date=date(2026, 9, 19), status="abnormal",
        reservation_count=1, usage_count=1, quota_record_count=1, anomaly_count=1,
        started_at=created_at,
    )
    reservation = QuotaReservation(
        reservation_id="reservation-1", user_id="user-1", key_id="key-1", project_id="project-1",
        department_id="dept-1", model="model-1", estimated_tokens=20, actual_tokens=10,
        estimated_cost_cny=0.02, actual_cost_cny=0.01, budget_accounted=True, price_type="token",
        input_price=1, output_price=2, request_price=0, status="committed", created_at=created_at,
        updated_at=created_at, expires_at=created_at,
    )
    usage = UsageLog(
        id=7, log_id="usage-1", user_id="user-1", key_id="key-1", model="model-1",
        project_id="project-1", department_id="dept-1", cost_cny=0.01, reservation_id="reservation-1",
        prompt_tokens=6, completion_tokens=4, total_tokens=10, latency_ms=12, status_code=200,
        created_at=created_at,
    )
    quota = QuotaRecord(
        id=9, record_id="quota-1", user_id="user-1", type=QuotaRecordType.decrease, amount=10,
        balance_before=100, balance_after=90, source="api_call", reason="request", created_at=created_at,
    )
    item = BillingReconcileItem(
        item_id="item-details", report_id=report.report_id, anomaly_type="committed_usage_mismatch",
        reservation_id=reservation.reservation_id, usage_log_id=usage.id, quota_record_id=quota.record_id,
        user_id="user-1", detail="mismatch", created_at=created_at,
    )
    db.add_all([report, reservation, usage, quota, item])
    db.commit()
    app = FastAPI()
    app.include_router(billing.router, prefix="/admin/billing")
    app.dependency_overrides[get_db] = lambda: db
    app.dependency_overrides[require_admin] = lambda: object()

    response = TestClient(app).get("/admin/billing/reconcile/reports/report-details/items")

    assert response.status_code == 200, response.text
    sources = response.json()["items"][0]["sources"]
    assert sources["reservation"] == {
        "reservation_id": "reservation-1", "user_id": "user-1", "key_id": "key-1",
        "project_id": "project-1", "department_id": "dept-1", "model": "model-1",
        "status": "committed", "estimated_tokens": 20, "actual_tokens": 10,
        "estimated_cost_cny": 0.02, "actual_cost_cny": 0.01,
        "price_currency": "CNY", "exchange_rate": 1.0, "exchange_rate_date": None, "conversion_kind": None,
    }
    assert sources["usage"] == {
        "id": 7, "log_id": "usage-1", "reservation_id": "reservation-1", "user_id": "user-1",
        "key_id": "key-1", "channel_id": None, "model": "model-1", "api_type": "chat",
        "cost_cny": 0.01, "prompt_tokens": 6, "completion_tokens": 4, "total_tokens": 10,
        "status_code": 200,
        "price_currency": None, "exchange_rate": None, "exchange_rate_date": None, "conversion_kind": None,
    }
    assert sources["quota_record"] == {
        "record_id": "quota-1", "user_id": "user-1", "type": "decrease", "amount": 10,
        "balance_before": 100, "balance_after": 90, "source": "api_call", "reason": "request",
    }
    db.close()
    engine.dispose()
