"""管理员月预算配置与账本汇总。"""
import secrets
from datetime import date, datetime
from zoneinfo import ZoneInfo
from decimal import Decimal
from typing import Literal, List

from fastapi import APIRouter, Depends, HTTPException, Request, Query
from pydantic import BaseModel, Field, field_validator
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.dependencies import require_admin
from app.models.budget import Budget
from app.models.billing_reconcile import BillingReconcileItem, BillingReconcileReport
from app.models.quota_reservation import QuotaReservation
from app.models.user import User
from app.services.budget_service import BudgetService, current_month, month_bounds
from app.services.billing_reconcile_service import (
    BillingReconcileService, RECONCILE_COVERAGE_STARTED_AT, RECONCILE_GRACE_MINUTES,
)
from app.services.operation_log_service import record_operation
from app.utils.request import extract_client_ip

router = APIRouter()


def reconcile_meta():
    return {
        'coverage_started_at': RECONCILE_COVERAGE_STARTED_AT.isoformat(),
        'timezone': 'Asia/Shanghai',
        'grace_minutes': RECONCILE_GRACE_MINUTES,
        'history_rule': '覆盖起点前的用量不因缺少预扣或费用而误报',
    }


def report_response(row):
    return {field: getattr(row, field) for field in (
        'report_id', 'business_date', 'status', 'reservation_count', 'usage_count',
        'quota_record_count', 'anomaly_count', 'started_at', 'finished_at', 'error_message')}


class BudgetSave(BaseModel):
    amount_usd: Decimal = Field(ge=0, max_digits=18, decimal_places=8)
    thresholds: List[int] = Field(default_factory=lambda: [80, 90, 100], min_length=1, max_length=100)
    policy: Literal['alert', 'block'] = 'block'
    enabled: bool = True

    @field_validator('thresholds', mode='before')
    @classmethod
    def valid_thresholds(cls, values):
        if not isinstance(values, list) or any(type(t) is not int or not 1 <= t <= 100 for t in values):
            raise ValueError('阈值必须为 1 到 100 的整数')
        if len(set(values)) != len(values):
            raise ValueError('阈值不能重复')
        return sorted(values)


def validate_month(month):
    try:
        month_bounds(month)
        if len(month) != 7:
            raise ValueError()
    except (ValueError, OverflowError):
        raise HTTPException(422, '月份格式必须为 YYYY-MM')
    return month


def response(db, row):
    service = BudgetService(db)
    # 配置列表展示名称无需持有组织锁。
    from app.models.project import Project
    from app.models.organization import Department
    scope = db.get(Project if row.scope_type == 'project' else Department, row.scope_id)
    return {**{field: getattr(row, field) for field in (
        'budget_id', 'scope_type', 'scope_id', 'month', 'amount_usd', 'thresholds', 'policy', 'enabled')},
        'scope_name': scope.name if scope else row.scope_id, **service.summary(row)}


@router.get('/budgets')
async def list_budgets(month: str = Query(default=None), admin: User = Depends(require_admin), db: Session = Depends(get_db)):
    month = validate_month(month or current_month())
    rows = db.query(Budget).filter_by(month=month).order_by(Budget.scope_type, Budget.scope_id).all()
    return {'month': month, 'items': [response(db, row) for row in rows]}


@router.get('/reservations')
async def list_reservations(month: str = Query(default=None), status: str = Query(default=None),
                            admin: User = Depends(require_admin), db: Session = Depends(get_db)):
    month = validate_month(month or current_month())
    start, end = month_bounds(month)
    query = db.query(QuotaReservation).filter(
        QuotaReservation.created_at >= start, QuotaReservation.created_at < end)
    if status:
        if status not in {'reserved', 'committed', 'released', 'expired'}:
            raise HTTPException(422, '预扣状态无效')
        query = query.filter(QuotaReservation.status == status)
    rows = query.order_by(QuotaReservation.created_at.desc()).limit(200).all()
    return {'month': month, 'items': [{field: getattr(row, field) for field in (
        'reservation_id', 'user_id', 'key_id', 'project_id', 'department_id', 'model',
        'estimated_tokens', 'actual_tokens', 'estimated_cost_usd', 'actual_cost_usd',
        'status', 'created_at', 'updated_at', 'expires_at')} for row in rows]}


@router.get('/reconcile/reports')
async def list_reconcile_reports(page: int = Query(1, ge=1), page_size: int = Query(20, ge=1, le=100),
                                 admin: User = Depends(require_admin), db: Session = Depends(get_db)):
    query = db.query(BillingReconcileReport)
    total = query.count()
    rows = query.order_by(BillingReconcileReport.business_date.desc()).offset((page - 1) * page_size).limit(page_size).all()
    return {'total': total, 'items': [report_response(row) for row in rows], **reconcile_meta()}


@router.get('/reconcile/reports/{report_id}/items')
async def list_reconcile_items(report_id: str, page: int = Query(1, ge=1), page_size: int = Query(20, ge=1, le=100),
                               anomaly_type: str = Query(default=None), admin: User = Depends(require_admin),
                               db: Session = Depends(get_db)):
    if db.get(BillingReconcileReport, report_id) is None:
        raise HTTPException(404, '对账报告不存在')
    query = db.query(BillingReconcileItem).filter_by(report_id=report_id)
    if anomaly_type:
        query = query.filter(BillingReconcileItem.anomaly_type == anomaly_type)
    total = query.count()
    rows = query.order_by(BillingReconcileItem.created_at, BillingReconcileItem.item_id).offset((page - 1) * page_size).limit(page_size).all()
    fields = ('item_id', 'anomaly_type', 'reservation_id', 'usage_log_id', 'quota_record_id', 'user_id',
              'expected_value', 'actual_value', 'detail', 'created_at')
    return {'total': total, 'items': [{field: getattr(row, field) for field in fields} for row in rows]}


@router.post('/reconcile/run/{business_date}')
async def run_reconcile(business_date: date, request: Request, admin: User = Depends(require_admin),
                        db: Session = Depends(get_db)):
    if business_date >= datetime.now(ZoneInfo('Asia/Shanghai')).date():
        raise HTTPException(422, '只能对账已结束的业务日')
    report = BillingReconcileService(db).run(business_date)
    record_operation(db=db, operator=admin, action='reconcile', target_type='billing_reconcile',
                     target_id=report.report_id, detail={'business_date': business_date.isoformat()},
                     ip_address=extract_client_ip(request))
    return report_response(report)


@router.put('/budgets/{scope_type}/{scope_id}/{month}')
async def save_budget(scope_type: Literal['project', 'department'], scope_id: str, month: str,
                      data: BudgetSave, request: Request, admin: User = Depends(require_admin), db: Session = Depends(get_db)):
    validate_month(month)
    db.rollback()  # 结束鉴权只读快照，归属行锁后读取预算配置。
    service = BudgetService(db)
    try:
        if not service.lock_scope(scope_type, scope_id):
            raise HTTPException(404, '项目或部门不存在')
        row = db.query(Budget).filter_by(scope_type=scope_type, scope_id=scope_id, month=month).populate_existing().first()
        if row is None:
            row = Budget(budget_id=secrets.token_hex(16), scope_type=scope_type, scope_id=scope_id, month=month)
            db.add(row)
        for field, value in data.model_dump().items():
            setattr(row, field, value)
        db.commit()
    except BaseException:
        db.rollback()
        raise
    record_operation(db=db, operator=admin, action='update', target_type='budget', target_id=row.budget_id,
                     detail={**data.model_dump(mode='json'), 'scope_type': scope_type, 'scope_id': scope_id, 'month': month},
                     ip_address=extract_client_ip(request))
    return response(db, row)
