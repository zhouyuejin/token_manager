"""Read-only daily reconciliation of reservation, usage, and quota ledgers."""
import json
import secrets
from datetime import date, datetime, time, timedelta
from decimal import Decimal
from zoneinfo import ZoneInfo
from sqlalchemy.exc import IntegrityError

from app.models.billing_reconcile import BillingReconcileItem, BillingReconcileReport
from app.models.quota_record import QuotaRecord
from app.models.quota_reservation import QuotaReservation
from app.models.usage_log import UsageLog

BEIJING = ZoneInfo("Asia/Shanghai")
RECONCILE_COVERAGE_STARTED_AT = datetime(2026, 9, 20, 0, 0, 0)
RECONCILE_GRACE_MINUTES = 30


def business_day_bounds(value: date):
    start = datetime.combine(value, time.min, BEIJING)
    end = start + timedelta(days=1)
    return start.replace(tzinfo=None), end.replace(tzinfo=None)


class BillingReconcileService:
    def __init__(self, db):
        self.db = db

    def _item(self, report_id, anomaly_type, detail, *, reservation=None, usage=None, quota=None,
              expected=None, actual=None, now=None):
        self.db.add(BillingReconcileItem(
            item_id=secrets.token_hex(16), report_id=report_id, anomaly_type=anomaly_type,
            reservation_id=getattr(reservation, "reservation_id", None),
            usage_log_id=getattr(usage, "id", None),
            quota_record_id=getattr(quota, "record_id", None),
            user_id=(getattr(reservation, "user_id", None) or getattr(usage, "user_id", None)
                     or getattr(quota, "user_id", None)),
            expected_value=None if expected is None else str(expected),
            actual_value=None if actual is None else str(actual), detail=detail, created_at=now or datetime.utcnow(),
        ))

    def run(self, business_date: date, *, now=None):
        now = now or datetime.utcnow()
        start, end = business_day_bounds(business_date)
        report = self.db.query(BillingReconcileReport).filter_by(business_date=business_date).with_for_update().first()
        if report is None:
            report = BillingReconcileReport(
                report_id=secrets.token_hex(16), business_date=business_date,
                status="running", started_at=now,
            )
            self.db.add(report)
            try:
                self.db.flush()
            except IntegrityError:
                self.db.rollback()
                report = self.db.query(BillingReconcileReport).filter_by(
                    business_date=business_date).with_for_update().one()
        report.status, report.started_at, report.finished_at, report.error_message = "running", now, None, None
        self.db.query(BillingReconcileItem).filter_by(report_id=report.report_id).delete(synchronize_session=False)
        self.db.flush()
        try:
            reservations = self.db.query(QuotaReservation).filter(
                QuotaReservation.created_at >= start, QuotaReservation.created_at < end).yield_per(500)
            usage_query = self.db.query(UsageLog).filter(
                UsageLog.created_at >= start, UsageLog.created_at < end).order_by(UsageLog.created_at, UsageLog.id)
            quota_query = self.db.query(QuotaRecord).filter(
                QuotaRecord.created_at >= start, QuotaRecord.created_at < end
            ).order_by(QuotaRecord.user_id, QuotaRecord.created_at, QuotaRecord.id)
            usage_by_reservation = {}
            usage_count = 0
            for usage in usage_query.yield_per(500):
                usage_count += 1
                if usage.reservation_id and 200 <= usage.status_code < 400:
                    usage_by_reservation[usage.reservation_id] = usage
            reservation_ids = set()
            reservation_count = 0
            for reservation in reservations:
                reservation_count += 1
                reservation_ids.add(reservation.reservation_id)
                usage = usage_by_reservation.get(reservation.reservation_id)
                if reservation.status == "committed":
                    if usage is None:
                        self._item(report.report_id, "committed_missing_usage", "已结算预扣缺少成功用量明细", reservation=reservation, now=now)
                    else:
                        expected = {
                            "user_id": reservation.user_id, "key_id": reservation.key_id,
                            "project_id": reservation.project_id, "department_id": reservation.department_id,
                            "model": reservation.model, "tokens": reservation.actual_tokens,
                            "cost_usd": f"{Decimal(reservation.actual_cost_usd):.8f}",
                        }
                        actual = {
                            "user_id": usage.user_id, "key_id": usage.key_id, "project_id": usage.project_id,
                            "department_id": usage.department_id, "model": usage.model, "tokens": usage.total_tokens,
                            "cost_usd": f"{Decimal(usage.cost_usd):.8f}",
                        }
                        if expected != actual:
                            self._item(report.report_id, "committed_usage_mismatch", "预扣结算与最终成功用量不一致",
                                       reservation=reservation, usage=usage, expected=json.dumps(expected, ensure_ascii=False),
                                       actual=json.dumps(actual, ensure_ascii=False), now=now)
                if reservation.status == "reserved" and reservation.expires_at < now - timedelta(minutes=RECONCILE_GRACE_MINUTES):
                    self._item(report.report_id, "expired_lease_still_reserved", "预扣租约超过宽限期仍未终结", reservation=reservation, now=now)
                invalid_terminal = (
                    reservation.status == "committed" and (reservation.actual_tokens is None or reservation.actual_cost_usd is None)
                ) or (
                    reservation.status in {"released", "expired"} and
                    ((reservation.actual_tokens or 0) != 0 or Decimal(reservation.actual_cost_usd or 0) != Decimal("0"))
                )
                if invalid_terminal:
                    self._item(report.report_id, "terminal_reservation_invalid", "终态预扣的实际 token 或费用不合法", reservation=reservation, now=now)
            referenced_ids = {row[0] for row in self.db.query(UsageLog.reservation_id).filter(
                UsageLog.created_at >= start, UsageLog.created_at < end, UsageLog.reservation_id.isnot(None)).distinct()}
            existing_ids = {row[0] for row in self.db.query(QuotaReservation.reservation_id).filter(
                QuotaReservation.reservation_id.in_(referenced_ids)).all()} if referenced_ids else set()
            for usage in usage_query.yield_per(500):
                if usage.created_at < RECONCILE_COVERAGE_STARTED_AT or not (200 <= usage.status_code < 400):
                    continue
                if usage.cost_usd is None:
                    self._item(report.report_id, "usage_missing_cost", "成功用量缺少 USD 费用", usage=usage, now=now)
                if (usage.cost_usd or 0) != 0 and (not usage.reservation_id or usage.reservation_id not in existing_ids):
                    self._item(report.report_id, "usage_missing_reservation", "成功计费用量缺少有效预扣", usage=usage, now=now)
            previous = {}
            quota_record_count = 0
            for quota in quota_query.yield_per(500):
                quota_record_count += 1
                broken = quota.balance_after != quota.balance_before + (quota.amount if quota.type.value == "increase" else -quota.amount)
                if quota.user_id in previous and quota.balance_before != previous[quota.user_id].balance_after:
                    broken = True
                if broken:
                    self._item(report.report_id, "quota_record_chain_broken", "额度流水余额链不连续", quota=quota, now=now)
                previous[quota.user_id] = quota
            report.reservation_count = reservation_count
            report.usage_count = usage_count
            report.quota_record_count = quota_record_count
            report.anomaly_count = self.db.query(BillingReconcileItem).filter_by(report_id=report.report_id).count()
            report.status = "abnormal" if report.anomaly_count else "normal"
            report.finished_at = now
            self.db.commit()
            self.db.refresh(report)
            return report
        except Exception as exc:
            self.db.rollback()
            report = self.db.query(BillingReconcileReport).filter_by(business_date=business_date).first()
            if report is None:
                report = BillingReconcileReport(report_id=secrets.token_hex(16), business_date=business_date, started_at=now)
                self.db.add(report)
            self.db.query(BillingReconcileItem).filter_by(report_id=report.report_id).delete(synchronize_session=False)
            report.status, report.finished_at, report.error_message = "failed", now, str(exc)[:1000]
            report.reservation_count = report.usage_count = report.quota_record_count = report.anomaly_count = 0
            self.db.commit()
            raise
