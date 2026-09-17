"""API Key 短周期错误计数；第一版只冻结认证/IP 异常。"""
import hashlib
import json
import secrets
from datetime import datetime

from loguru import logger

from app.models.api_key import ApiKey, ApiKeyStatus
from app.models.notification import Notification, NotificationType
from app.models.operation_log import OperationLog
from app.models.user import User, UserRole
from app.services.rate_limit_service import get_rate_limit_redis_client

ERROR_KINDS = ('auth', 'ip_mismatch', 'quota', 'rate_limit', 'upstream_4xx')

# 计数、裁剪和 TTL 在同一个脚本中完成，避免并发丢计数或留下永久计数器。
_RECORD_ERROR = """
local now = tonumber(ARGV[1])
if now < 0 then
    local t = redis.call('TIME')
    now = tonumber(t[1]) + tonumber(t[2]) / 1000000
end
local seq = redis.call('INCR', KEYS[3])
redis.call('EXPIRE', KEYS[3], 90)
local member = tostring(seq)
redis.call('ZREMRANGEBYSCORE', KEYS[1], '-inf', now - 60)
redis.call('ZADD', KEYS[1], now, member)
redis.call('EXPIRE', KEYS[1], 90)
local streak = 1
if redis.call('HGET', KEYS[4], 'kind') == ARGV[3] then
    streak = tonumber(redis.call('HGET', KEYS[4], 'count') or '0') + 1
end
redis.call('HSET', KEYS[4], 'kind', ARGV[3], 'count', streak)
redis.call('EXPIRE', KEYS[4], 60)
if ARGV[2] == '1' then
    redis.call('ZREMRANGEBYSCORE', KEYS[2], '-inf', now - 60)
    redis.call('ZADD', KEYS[2], now, member)
    redis.call('EXPIRE', KEYS[2], 90)
    return redis.call('ZCARD', KEYS[2])
end
return 0
"""


def _scope(api_key):
    # 轮换后隔离旧密钥的错误窗口；Redis 中不存明文密钥。
    fingerprint = hashlib.sha256(api_key.api_key.encode()).hexdigest()[:16]
    return f'key-errors:{api_key.key_id}:{fingerprint}'


def reset_api_key_errors(api_key, redis_client=None):
    client = redis_client if redis_client is not None else get_rate_limit_redis_client()
    scope = _scope(api_key)
    client.delete(*[f'{scope}:{kind}' for kind in ERROR_KINDS],
                  f'{scope}:abnormal', f'{scope}:seq', f'{scope}:streak')


def record_api_key_success(api_key, redis_client=None):
    try:
        client = redis_client if redis_client is not None else get_rate_limit_redis_client()
        client.delete(f'{_scope(api_key)}:streak')
    except Exception:
        logger.warning('API Key 连续错误计数重置失败')


def record_api_key_error(db, api_key, kind, redis_client=None, now=None):
    if kind not in ERROR_KINDS or not getattr(api_key, 'key_id', None):
        return False
    if getattr(api_key, 'frozen_at', None):
        return False
    try:
        client = redis_client if redis_client is not None else get_rate_limit_redis_client()
        scope = _scope(api_key)
        count = client.eval(_RECORD_ERROR, 4, f'{scope}:{kind}', f'{scope}:abnormal',
                            f'{scope}:seq', f'{scope}:streak',
                            -1 if now is None else now, int(kind in ('auth', 'ip_mismatch')), kind)
    except Exception:
        # Redis 不可用时保留原有认证/拒绝行为，不把控制组件故障变成全站阻断。
        logger.warning('API Key 错误计数失败，保留原请求处理结果')
        return False
    if count < 50:
        return False

    frozen_at = datetime.utcnow()
    reason = '60 秒内认证失败或 IP 不匹配累计达到 50 次'
    try:
        # 条件更新保证多 worker 只有一个完成冻结并发送通知，且不覆盖吊销/手动禁用。
        changed = db.query(ApiKey).filter(
            ApiKey.key_id == api_key.key_id,
            ApiKey.api_key == api_key.api_key,
            ApiKey.status == ApiKeyStatus.active,
            ApiKey.frozen_at.is_(None),
        ).update({'status': ApiKeyStatus.disabled, 'frozen_at': frozen_at,
                  'frozen_reason': reason}, synchronize_session=False)
        if not changed:
            db.rollback()
            return False
        recipients = {api_key.user_id}
        recipients.update(user.user_id for user in db.query(User).filter(User.role == UserRole.admin).all())
        metadata = json.dumps({'key_id': api_key.key_id, 'reason': reason,
                               'frozen_at': frozen_at.isoformat() + 'Z'})
        for user_id in recipients:
            db.add(Notification(
                notif_id=f'notif_{secrets.token_hex(8)}', user_id=user_id,
                type=NotificationType.system, title='API Key 已自动冻结',
                content=f'API Key {api_key.key_id} 已自动冻结：{reason}。请联系管理员核查后解除冻结。',
                extra_data=metadata, is_read=0,
            ))
        db.add(OperationLog(
            log_id=f'log_{secrets.token_hex(12)}', operator_id='system', operator_name='系统',
            action='auto_freeze', target_type='api_key', target_id=api_key.key_id,
            detail=metadata,
        ))
        db.commit()
        db.expire_all()
        return True
    except Exception:
        db.rollback()
        logger.warning('API Key 自动冻结事务失败')
        return False
