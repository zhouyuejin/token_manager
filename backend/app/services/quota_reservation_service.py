"""数据库为账务事实来源，用户行锁 + Redis Lua 原子准入。"""
import secrets
import logging
from contextlib import contextmanager
from threading import Event, Thread
from datetime import datetime, timedelta
from decimal import Decimal, ROUND_CEILING

from fastapi import HTTPException
from redis.exceptions import RedisError
from sqlalchemy import update
from sqlalchemy.orm import sessionmaker

from app.models.user import User, UserRole
from app.models.api_key import ApiKey
from app.models.model import Model
from app.models.quota_reservation import QuotaReservation
from app.services.rate_limit_service import get_rate_limit_redis_client
from app.services.budget_service import BudgetService, current_month


LEASE_SECONDS = 300
logger = logging.getLogger(__name__)
_ADMIT = """
-- 调用方持有数据库用户行锁；每次从 durable ledger 重建可用量。
local available = tonumber(ARGV[1])
local amount = tonumber(ARGV[2])
redis.call('SET', KEYS[1], ARGV[1], 'EX', 60)
if available < amount then return 0 end
redis.call('DECRBY', KEYS[1], ARGV[2])
return 1
"""


def cost(row, tokens):
    if row.price_type == 'request':
        amount = Decimal(row.request_price)
    else:
        amount = (Decimal(tokens.get('prompt_tokens', 0)) * Decimal(row.input_price)
            + Decimal(tokens.get('completion_tokens', 0)) * Decimal(row.output_price)) / 1000
    # 最小记账单位为 USD 1e-8；预扣、结算和日志采用一致的向上舍入。
    return amount.quantize(Decimal('0.00000001'), rounding=ROUND_CEILING)


def estimate_request(request_data):
    output = request_data.get('max_tokens')
    output = 1024 if output is None else output
    if not isinstance(output, int) or isinstance(output, bool) or output <= 0:
        raise HTTPException(422, 'max_tokens 必须为正整数')
    # 注意:不在此写回 request_data['max_tokens']。配额预扣的默认上限仅用于估算,
    # 上游调用仍按调用方传入的 max_tokens(或省略让模型自决),避免配额默认值污染实际请求。
    # 字节数涵盖中文和 role；上游消息模板开销不在 content 中，额外预留 256 tokens。
    prompt = 256 + sum(len(str(m.get('content') or '').encode('utf-8'))
                      + len(str(m.get('role') or '').encode('utf-8')) + 16
                      for m in request_data.get('messages', []))
    return prompt, output


class QuotaReservationService:
    def __init__(self, db):
        self.db = db

    def _user(self, uid):
        return self.db.query(User).filter_by(user_id=uid).populate_existing().with_for_update().one()

    def reserve(self, user, key, model_id, request_data, attribution):
        prompt, output = estimate_request(request_data)
        amount = prompt + output
        uid, kid = user.user_id, key.key_id
        # 结束鉴权/归因只读事务；组织锁取得后才建立新快照，避免旧快照漏掉并发预扣。
        self.db.rollback()
        try:
            locked = self._user(uid)
            now = datetime.utcnow()
            budgets = BudgetService(self.db).lock_budgets(attribution, current_month(now))
            outstanding = self.db.query(QuotaReservation).filter_by(user_id=uid, status='reserved').populate_existing().all()
            available = locked.quota - locked.quota_used - sum(r.estimated_tokens for r in outstanding)
            unlimited = locked.role == UserRole.admin or locked.quota < 0
            if not get_rate_limit_redis_client().eval(_ADMIT, 1, 'quota:admit:' + uid,
                                                    amount if unlimited else available, amount):
                raise HTTPException(403, f'额度不足，可用 {max(available, 0)} tokens（已扣除预扣）')
            model = self.db.query(Model).filter_by(model_id=model_id).first()
            if not model:
                raise HTTPException(404, '模型不存在，无法预扣')
            row = QuotaReservation(
                reservation_id=secrets.token_hex(16), user_id=uid, key_id=kid, model=model_id,
                **attribution, estimated_tokens=amount,
                price_type=getattr(model.price_type, 'value', model.price_type),
                input_price=model.price_per_1k_input, output_price=model.price_per_1k_output,
                request_price=model.price_per_request, status='reserved',
                created_at=now, updated_at=now, expires_at=now + timedelta(seconds=LEASE_SECONDS))
            row.estimated_cost_usd = cost(row, {'prompt_tokens': prompt, 'completion_tokens': output})
            BudgetService(self.db).admit(budgets, row.estimated_cost_usd)
            self.db.add(row)
            reservation_id = row.reservation_id
            self.db.commit()
            return reservation_id
        except RedisError as exc:
            self.db.rollback()
            raise HTTPException(503, '预扣服务不可用，请稍后重试') from exc
        except BaseException:
            self.db.rollback()
            raise

    def _locked(self, rid):
        row = self.db.get(QuotaReservation, rid)
        if row is None:
            return None, None
        user = self._user(row.user_id)
        BudgetService(self.db).lock_budgets({'project_id': row.project_id, 'department_id': row.department_id}, current_month(row.created_at))
        row = self.db.query(QuotaReservation).filter_by(reservation_id=rid).populate_existing().with_for_update().one()
        return user, row

    def commit(self, rid, tokens):
        try:
            user, row = self._locked(rid)
            if row is None or row.status != 'reserved':
                self.db.rollback()
                return False
            actual = int(tokens.get('total_tokens', 0))
            if actual < 0:
                raise ValueError('Invalid upstream token usage')
            if actual > row.estimated_tokens:
                logger.error('上游用量超过预扣上限，reservation_id=%s, reserved=%s, actual=%s',
                             rid, row.estimated_tokens, actual)
                raise HTTPException(502, '上游用量超过预扣上限，拒绝结算，请联系管理员检查模型配置')
            row.actual_tokens = actual
            row.actual_cost_usd = cost(row, tokens)
            if row.actual_cost_usd > row.estimated_cost_usd:
                raise HTTPException(502, '上游费用超过预扣上限，拒绝结算，请联系管理员检查模型配置')
            row.status = 'committed'
            row.budget_accounted = True
            row.updated_at = datetime.utcnow()
            self.db.execute(update(User).where(User.user_id == user.user_id).values(quota_used=User.quota_used + actual))
            self.db.execute(update(ApiKey).where(ApiKey.key_id == row.key_id).values(last_used_at=datetime.utcnow()))
            self.db.commit()
            return True
        except BaseException:
            self.db.rollback()
            raise

    def release(self, rid, expired=False):
        if not rid:
            return
        try:
            _, row = self._locked(rid)
            if row and row.status == 'reserved' and (not expired or row.expires_at <= datetime.utcnow()):
                row.status = 'expired' if expired else 'released'
                row.actual_tokens = 0
                row.actual_cost_usd = 0
                row.updated_at = datetime.utcnow()
            self.db.commit()
        except BaseException:
            self.db.rollback()
            raise

    def renew(self, rid):
        _, row = self._locked(rid)
        if not row or row.status != 'reserved':
            self.db.rollback()
            raise RuntimeError('预扣已过期或释放，终止上游请求')
        now = datetime.utcnow()
        row.updated_at = now
        row.expires_at = now + timedelta(seconds=LEASE_SECONDS)
        self.db.commit()

    @contextmanager
    def lease(self, rid):
        if not rid:
            yield
            return
        # 独立 session：同步上游读取可能阻塞，不能靠 chunk 到达才能续期。
        sessions = sessionmaker(bind=self.db.get_bind())
        stopped = Event()
        errors = []
        def renew():
            with sessions() as db:
                QuotaReservationService(db).renew(rid)
        def heartbeat():
            while not stopped.wait(30):
                try:
                    renew()
                except Exception as exc:
                    errors.append(exc)
                    return
        renew()
        thread = Thread(target=heartbeat, daemon=True, name='quota-lease')
        thread.start()
        try:
            yield
            if errors:
                raise RuntimeError('预扣续期失败') from errors[0]
        finally:
            stopped.set()
            thread.join(timeout=1)

    def expire(self):
        ids = [r[0] for r in self.db.query(QuotaReservation.reservation_id).filter(
            QuotaReservation.status == 'reserved', QuotaReservation.expires_at <= datetime.utcnow()).limit(1000).all()]
        self.db.rollback()
        for rid in ids:
            self.release(rid, expired=True)
