import time
from typing import Optional, TypedDict, Union

from app.core.config import settings
from app.services.metrics import rate_limit_rejections


_redis_client = None


class RateLimitDecision(TypedDict, total=False):
    allowed: bool
    reason: str
    retry_after_ms: int
    detail: str
    concurrency_key: Optional[Union[str, list[str]]]


def get_rate_limit_redis_client():
    global _redis_client
    if _redis_client is None:
        import redis

        _redis_client = redis.from_url(settings.REDIS_URL, decode_responses=True)
    return _redis_client


def check_proxy_rate_limit(redis_client, api_key, user, model: str, estimated_tokens: int, now: Optional[float] = None) -> RateLimitDecision:
    now = time.time() if now is None else now
    user_id = user.user_id
    scopes = [("user", user_id, user)]
    if api_key is not None:
        scopes.insert(0, ("key", f"{user_id}:{api_key.key_id}:{model}", api_key))

    concurrency_keys = []
    for scope_type, scope, limits in scopes:
        concurrency_limit = int(getattr(limits, "concurrency_limit", 0) or 0)
        if concurrency_limit <= 0:
            continue
        concurrency_key = f"rl:concurrency:{scope}" if scope_type == "key" else f"rl:concurrency:user:{scope}"
        current = redis_client.incr(concurrency_key)
        redis_client.expire(concurrency_key, 300)
        if current > concurrency_limit:
            redis_client.decr(concurrency_key)
            release_proxy_concurrency(redis_client, concurrency_keys)
            return {
                "allowed": False,
                "reason": "concurrency_limit" if scope_type == "key" else "user_concurrency_limit",
                "retry_after_ms": 1000,
                "detail": f"{'用户级' if scope_type == 'user' else 'Key'}并发请求数已超过限制",
                "concurrency_key": None,
            }
        concurrency_keys.append(concurrency_key)

    for window_name, limit_attr, window_seconds, amount in (
        ("qps", "qps_limit", 1, 1),
        ("rpm", "rpm_limit", 60, 1),
        ("tpm", "tpm_limit", 60, estimated_tokens),
    ):
        for scope_type, scope, limits in scopes:
            limit = int(getattr(limits, limit_attr, 0) or 0)
            if limit <= 0:
                continue

            bucket = int(now // window_seconds)
            redis_key = (f"rl:{window_name}:{scope}:{bucket}" if scope_type == "key"
                         else f"rl:{window_name}:user:{scope}:{bucket}")
            count = redis_client.incr(redis_key, amount)
            redis_client.expire(redis_key, window_seconds + 1)

            if count > limit:
                reason = f"{window_name}_limit" if scope_type == "key" else f"user_{window_name}_limit"
                rate_limit_rejections.labels(window=window_name if scope_type == "key" else reason).inc()
                release_proxy_concurrency(redis_client, concurrency_keys)
                retry_after_ms = int(((bucket + 1) * window_seconds - now) * 1000)
                prefix = "用户级 " if scope_type == "user" else ""
                return {
                    "allowed": False,
                    "reason": reason,
                    "retry_after_ms": max(retry_after_ms, 1),
                    "detail": f"{prefix}{window_name.upper()} 已超过限制",
                    "concurrency_key": None,
                }

    return {
        "allowed": True,
        "reason": "allowed",
        "retry_after_ms": 0,
        "detail": "",
        "concurrency_key": concurrency_keys,
    }


def release_proxy_concurrency(redis_client, concurrency_key: Optional[Union[str, list[str]]]) -> None:
    if not concurrency_key:
        return
    for key in concurrency_key if isinstance(concurrency_key, list) else [concurrency_key]:
        try:
            redis_client.decr(key)
        except Exception:
            pass
