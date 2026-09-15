import time
from typing import Optional, TypedDict

from app.core.config import settings


_redis_client = None


class RateLimitDecision(TypedDict, total=False):
    allowed: bool
    reason: str
    retry_after_ms: int
    detail: str
    concurrency_key: Optional[str]


def get_rate_limit_redis_client():
    global _redis_client
    if _redis_client is None:
        import redis

        _redis_client = redis.from_url(settings.REDIS_URL, decode_responses=True)
    return _redis_client


def check_proxy_rate_limit(redis_client, api_key, model: str, estimated_tokens: int, now: Optional[float] = None) -> RateLimitDecision:
    now = time.time() if now is None else now
    key_id = api_key.key_id
    user_id = api_key.user_id
    scope = f"{user_id}:{key_id}:{model}"

    concurrency_key = None
    concurrency_limit = int(getattr(api_key, "concurrency_limit", 0) or 0)
    if concurrency_limit > 0:
        concurrency_key = f"rl:concurrency:{scope}"
        current = redis_client.incr(concurrency_key)
        redis_client.expire(concurrency_key, 300)
        if current > concurrency_limit:
            redis_client.decr(concurrency_key)
            return {
                "allowed": False,
                "reason": "concurrency_limit",
                "retry_after_ms": 1000,
                "detail": "并发请求数已超过限制",
                "concurrency_key": None,
            }

    for window_name, limit_attr, window_seconds, amount in (
        ("qps", "qps_limit", 1, 1),
        ("rpm", "rpm_limit", 60, 1),
        ("tpm", "tpm_limit", 60, estimated_tokens),
    ):
        limit = int(getattr(api_key, limit_attr, 0) or 0)
        if limit <= 0:
            continue

        bucket = int(now // window_seconds)
        redis_key = f"rl:{window_name}:{scope}:{bucket}"
        count = redis_client.incr(redis_key, amount)
        redis_client.expire(redis_key, window_seconds + 1)

        if count > limit:
            if concurrency_key:
                redis_client.decr(concurrency_key)
            retry_after_ms = int(((bucket + 1) * window_seconds - now) * 1000)
            return {
                "allowed": False,
                "reason": f"{window_name}_limit",
                "retry_after_ms": max(retry_after_ms, 1),
                "detail": f"{window_name.upper()} 已超过限制",
                "concurrency_key": None,
            }

    return {
        "allowed": True,
        "reason": "allowed",
        "retry_after_ms": 0,
        "detail": "",
        "concurrency_key": concurrency_key,
    }


def release_proxy_concurrency(redis_client, concurrency_key: Optional[str]) -> None:
    if not concurrency_key:
        return
    try:
        redis_client.decr(concurrency_key)
    except Exception:
        pass
