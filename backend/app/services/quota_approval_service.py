"""Quota application domain action."""
import secrets

from fastapi import HTTPException

from app.models.quota_record import QuotaRecord, QuotaRecordType
from app.models.user import User


def apply_quota_approval(db, request):
    amount = request.payload.get('amount')
    if isinstance(amount, bool) or not isinstance(amount, int) or amount <= 0:
        raise HTTPException(422, '额度申请金额必须是正整数')
    user = db.query(User).filter_by(user_id=request.requester_user_id).with_for_update().first()
    if user is None:
        raise HTTPException(404, '申请用户不存在')
    if user.quota < 0:
        raise HTTPException(400, '无限制额度用户无需申请额度')
    before = user.quota
    user.quota += amount
    db.add(QuotaRecord(
        record_id=secrets.token_hex(16), user_id=user.user_id,
        type=QuotaRecordType.increase, amount=amount,
        balance_before=before, balance_after=user.quota,
        source='approval', reason=f'额度申请审批 {request.request_id}: {request.reason[:180]}',
        operator_id=request.approver_user_id,
    ))
