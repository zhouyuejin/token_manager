"""数据库行锁保护共享预算；站内告警独立提交、推送。"""
import json
import logging
import secrets
from datetime import datetime, timedelta
from decimal import Decimal

from fastapi import HTTPException
from sqlalchemy import or_

from app.models.budget import Budget, BudgetAlert
from app.models.organization import Department
from app.models.project import Project
from app.models.quota_reservation import QuotaReservation
from app.models.usage_log import UsageLog
from app.models.notification import Notification, NotificationType
from app.models.user import User, UserRole
from app.services.ws_manager import manager

logger = logging.getLogger(__name__)


def current_month(now=None):
    return ((now or datetime.utcnow()) + timedelta(hours=8)).strftime('%Y-%m')


def month_bounds(month):
    start = datetime.strptime(month, '%Y-%m')
    end = datetime(start.year + (start.month == 12), start.month % 12 + 1, 1)
    return start - timedelta(hours=8), end - timedelta(hours=8)


class BudgetService:
    def __init__(self, db):
        self.db = db

    def lock_scope(self, scope_type, scope_id):
        model, field = (Project, Project.project_id) if scope_type == 'project' else (Department, Department.dept_id)
        return self.db.query(model).filter(field == scope_id).populate_existing().with_for_update().first()

    def lock_budgets(self, attribution, month):
        # 锁顺序固定为用户（调用方）、部门、项目、预算，再读预扣记录。
        scopes = [('department', attribution.get('department_id')), ('project', attribution.get('project_id'))]
        for kind, sid in scopes:
            if sid:
                self.lock_scope(kind, sid)
        return self.db.query(Budget).filter(Budget.month == month, Budget.enabled.is_(True), or_(
            *[(Budget.scope_type == kind) & (Budget.scope_id == sid) for kind, sid in scopes if sid]
        )).order_by(Budget.scope_type, Budget.scope_id).populate_existing().with_for_update().all() if any(sid for _, sid in scopes) else []

    def summary(self, budget):
        start, end = month_bounds(budget.month)
        field = 'project_id' if budget.scope_type == 'project' else 'department_id'
        reservations = self.db.query(QuotaReservation).filter(
            getattr(QuotaReservation, field) == budget.scope_id,
            QuotaReservation.created_at >= start, QuotaReservation.created_at < end,
            QuotaReservation.status.in_(['reserved', 'committed']))
        legacy = self.db.query(UsageLog).filter(
            getattr(UsageLog, field) == budget.scope_id, UsageLog.reservation_id.is_(None),
            UsageLog.created_at >= start, UsageLog.created_at < end, UsageLog.status_code == 200)
        rows = reservations.all()
        # 升级前已结算记录仍按旧日志计费，避免无法关联的旧账本重复计算。
        used = sum((r.actual_cost_usd or Decimal(0) for r in rows if r.status == 'committed' and r.budget_accounted), Decimal(0))
        used += sum((r.cost_usd or Decimal(0) for r in legacy.all()), Decimal(0))
        reserved = sum((r.estimated_cost_usd for r in rows if r.status == 'reserved'), Decimal(0))
        return {'used_usd': used, 'reserved_usd': reserved,
                'remaining_usd': budget.amount_usd - used - reserved,
                'usage_percent': used / budget.amount_usd * 100 if budget.amount_usd else None}

    def admit(self, budgets, amount):
        for budget in budgets:
            # 准入从新事务开始，快照在组织/预算锁之后建立；不锁其它用户账本。
            remaining = self.summary(budget)['remaining_usd']
            if budget.policy == 'block' and (remaining < amount or remaining < 0):
                kind = '项目' if budget.scope_type == 'project' else '部门'
                raise HTTPException(403, f'{kind}月预算不足（{budget.month}），可用 ${max(remaining, 0):.8f}，本次预扣 ${amount:.8f}')

    async def check_alerts(self):
        ids = [bid for bid, in self.db.query(Budget.budget_id).filter(
            Budget.enabled.is_(True)).all()]
        self.db.rollback()
        for bid in ids:
            notifications = []
            try:
                budget = self.db.query(Budget).filter_by(budget_id=bid).populate_existing().with_for_update().one()
                if not budget.enabled:
                    self.db.rollback()
                    continue
                used = self.summary(budget)['used_usd']
                sent = {t for t, in self.db.query(BudgetAlert.threshold).filter_by(budget_id=bid).all()}
                thresholds = [t for t in budget.thresholds if t not in sent and used > 0 and used * 100 >= budget.amount_usd * t]
                if thresholds:
                    model = Project if budget.scope_type == 'project' else Department
                    owner = self.db.get(model, budget.scope_id)
                    recipients = {uid for uid, in self.db.query(User.user_id).filter(User.role == UserRole.admin).all()}
                    if owner and owner.owner_user_id:
                        recipients.add(owner.owner_user_id)
                    # 部门预算也通知本月有实际消费的项目负责人。
                    if budget.scope_type == 'department':
                        start, end = month_bounds(budget.month)
                        project_ids = {pid for pid, in self.db.query(QuotaReservation.project_id).filter(
                            QuotaReservation.department_id == budget.scope_id, QuotaReservation.status == 'committed',
                            QuotaReservation.created_at >= start, QuotaReservation.created_at < end).all()}
                        project_ids.update(pid for pid, in self.db.query(UsageLog.project_id).filter(
                            UsageLog.department_id == budget.scope_id, UsageLog.status_code == 200,
                            UsageLog.created_at >= start, UsageLog.created_at < end).all())
                        recipients.update(uid for uid, in self.db.query(Project.owner_user_id).filter(
                            Project.project_id.in_(project_ids), Project.owner_user_id.isnot(None)).all())
                    for threshold in thresholds:
                        self.db.add(BudgetAlert(alert_id=secrets.token_hex(16), budget_id=bid, threshold=threshold))
                        for uid in recipients:
                            kind = '项目' if budget.scope_type == 'project' else '部门'
                            notif = Notification(notif_id='notif_' + secrets.token_hex(8), user_id=uid,
                                type=NotificationType.system, title=f'{kind}预算达到 {threshold}%',
                                content=f'{owner.name if owner else budget.scope_id} {budget.month} 月预算 ${budget.amount_usd:.8f}，实际消费 ${used:.8f}。',
                                extra_data=json.dumps({'kind': 'budget_alert', 'budget_id': bid, 'month': budget.month,
                                                       'threshold': threshold, 'scope_type': budget.scope_type, 'scope_id': budget.scope_id}), is_read=0)
                            self.db.add(notif)
                            notifications.append(notif)
                self.db.flush()
                payloads = [(n.user_id, n.to_dict()) for n in notifications]
                self.db.commit()
            except Exception:
                self.db.rollback()
                logger.exception('预算告警持久化失败，后续调度重试 budget_id=%s', bid)
                continue
            for uid, payload in payloads:
                try:
                    await manager.send_to_user(uid, {'type': 'new_notification', 'notif': payload})
                except Exception:
                    logger.warning('预算告警已落库，WebSocket 推送失败 user_id=%s', uid, exc_info=True)
