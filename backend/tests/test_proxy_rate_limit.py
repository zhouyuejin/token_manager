import time
import uuid
from types import SimpleNamespace
from concurrent.futures import ThreadPoolExecutor

import pytest
from pydantic import ValidationError

from app.schemas.api_key import ApiKeyCreate, ApiKeyUpdate
from app.schemas.admin import AdminUserCreate, AdminUserUpdate
from app.services.rate_limit_service import (
    check_proxy_rate_limit,
    release_proxy_concurrency,
)


class FakeRedis:
    def __init__(self):
        self.values = {}
        self.expires = {}

    def incr(self, key, amount=1):
        self.values[key] = int(self.values.get(key, 0)) + amount
        return self.values[key]

    def decr(self, key):
        self.values[key] = int(self.values.get(key, 0)) - 1
        return self.values[key]

    def expire(self, key, seconds):
        self.expires[key] = seconds


def _api_key(user_id="usr_1", key_id="key_1", **limits):
    defaults = {
        "user_id": user_id,
        "key_id": key_id,
        "qps_limit": 0,
        "rpm_limit": 0,
        "tpm_limit": 0,
        "concurrency_limit": 0,
    }
    defaults.update(limits)
    return SimpleNamespace(**defaults)


def _user(user_id="usr_1", **limits):
    values = {"qps_limit": 0, "rpm_limit": 0, "tpm_limit": 0, "concurrency_limit": 0}
    values.update(limits)
    return SimpleNamespace(user_id=user_id, **values)


def test_allows_when_limits_are_empty():
    decision = check_proxy_rate_limit(FakeRedis(), _api_key(), _user(), "gpt", 100, now=1000.0)

    assert decision["allowed"] is True


def test_blocks_qps_limit():
    redis = FakeRedis()
    key = _api_key(qps_limit=1)

    assert check_proxy_rate_limit(redis, key, _user(), "gpt", 1, now=1000.1)["allowed"] is True
    decision = check_proxy_rate_limit(redis, key, _user(), "gpt", 1, now=1000.2)

    assert decision["allowed"] is False
    assert decision["reason"] == "qps_limit"
    assert decision["retry_after_ms"] > 0


def test_blocks_rpm_limit():
    redis = FakeRedis()
    key = _api_key(rpm_limit=1)

    assert check_proxy_rate_limit(redis, key, _user(), "gpt", 1, now=1000.0)["allowed"] is True
    decision = check_proxy_rate_limit(redis, key, _user(), "gpt", 1, now=1001.0)

    assert decision["allowed"] is False
    assert decision["reason"] == "rpm_limit"


def test_blocks_tpm_limit():
    redis = FakeRedis()
    key = _api_key(tpm_limit=100)

    assert check_proxy_rate_limit(redis, key, _user(), "gpt", 60, now=1000.0)["allowed"] is True
    decision = check_proxy_rate_limit(redis, key, _user(), "gpt", 50, now=1001.0)

    assert decision["allowed"] is False
    assert decision["reason"] == "tpm_limit"


def test_blocks_and_releases_concurrency_limit():
    redis = FakeRedis()
    key = _api_key(concurrency_limit=1)

    first = check_proxy_rate_limit(redis, key, _user(concurrency_limit=1), "gpt", 1, now=1000.0)
    second = check_proxy_rate_limit(redis, key, _user(concurrency_limit=1), "gpt", 1, now=1000.1)
    release_proxy_concurrency(redis, first["concurrency_key"])
    third = check_proxy_rate_limit(redis, key, _user(concurrency_limit=1), "gpt", 1, now=1000.2)

    assert first["allowed"] is True
    assert second["allowed"] is False
    assert second["reason"] == "concurrency_limit"
    assert third["allowed"] is True


def test_aggregates_user_qps_across_keys_and_models_but_isolates_users():
    redis = FakeRedis()
    user = _user(qps_limit=1)

    assert check_proxy_rate_limit(redis, _api_key(key_id="key_1"), user, "gpt", 1, now=1000.1)["allowed"] is True
    blocked = check_proxy_rate_limit(redis, _api_key(key_id="key_2"), user, "claude", 1, now=1000.2)
    other_user = check_proxy_rate_limit(
        redis, _api_key(user_id="usr_2", key_id="key_3"), _user("usr_2", qps_limit=1),
        "claude", 1, now=1000.2,
    )

    assert blocked["allowed"] is False
    assert blocked["reason"] == "user_qps_limit"
    assert other_user["allowed"] is True


@pytest.mark.parametrize(("limit_field", "limit", "first_amount", "second_amount", "reason"), [
    ("rpm_limit", 1, 1, 1, "user_rpm_limit"),
    ("tpm_limit", 100, 60, 50, "user_tpm_limit"),
])
def test_aggregates_user_rpm_and_tpm_across_keys(limit_field, limit, first_amount, second_amount, reason):
    redis = FakeRedis()
    user = _user(**{limit_field: limit})

    first = check_proxy_rate_limit(
        redis, _api_key(key_id="key_1"), user, "gpt", first_amount, now=1000.1,
    )
    second = check_proxy_rate_limit(
        redis, _api_key(key_id="key_2"), user, "claude", second_amount, now=1001.1,
    )

    assert first["allowed"] is True
    assert second["allowed"] is False
    assert second["reason"] == reason


def test_user_rate_limit_rejection_releases_key_concurrency():
    redis = FakeRedis()
    key = _api_key(concurrency_limit=1)
    limited_user = _user(qps_limit=1)
    assert check_proxy_rate_limit(redis, key, limited_user, "gpt", 1, now=1000.0)["allowed"] is True

    blocked_key = _api_key(key_id="key_2", concurrency_limit=1)
    blocked = check_proxy_rate_limit(redis, blocked_key, limited_user, "claude", 1, now=1000.1)
    retry = check_proxy_rate_limit(redis, blocked_key, limited_user, "claude", 1, now=1001.1)

    assert blocked["reason"] == "user_qps_limit"
    assert retry["allowed"] is True


def test_aggregates_user_concurrency_across_keys():
    redis = FakeRedis()
    user = _user(concurrency_limit=1)

    first = check_proxy_rate_limit(redis, _api_key(key_id="key_1"), user, "gpt", 1, now=1000.0)
    blocked = check_proxy_rate_limit(redis, _api_key(key_id="key_2"), user, "claude", 1, now=1000.1)

    assert first["allowed"] is True
    assert blocked["allowed"] is False
    assert blocked["reason"] == "user_concurrency_limit"
    release_proxy_concurrency(redis, first["concurrency_key"])


def test_user_concurrency_rejection_releases_key_concurrency():
    redis = FakeRedis()
    user = _user(concurrency_limit=1)
    first = check_proxy_rate_limit(
        redis, _api_key(key_id="key_1", concurrency_limit=1), user, "gpt", 1, now=1000.0,
    )
    next_key = _api_key(key_id="key_2", concurrency_limit=1)

    blocked = check_proxy_rate_limit(redis, next_key, user, "claude", 1, now=1000.1)
    release_proxy_concurrency(redis, first["concurrency_key"])
    retry = check_proxy_rate_limit(redis, next_key, user, "claude", 1, now=1000.2)

    assert blocked["reason"] == "user_concurrency_limit"
    assert retry["allowed"] is True


def test_user_qps_limit_uses_real_redis_counter():
    from app.services.rate_limit_service import get_rate_limit_redis_client

    client = get_rate_limit_redis_client()
    prefix = "test-user-rate:" + uuid.uuid4().hex + ":"

    class ScopedRedis:
        def incr(self, key, amount=1):
            return client.incr(prefix + key, amount)

        def expire(self, key, seconds):
            return client.expire(prefix + key, seconds)

        def decr(self, key):
            return client.decr(prefix + key)

    redis = ScopedRedis()
    user = _user(qps_limit=10)

    def attempt(index):
        return check_proxy_rate_limit(
            redis, _api_key(key_id=f"key_{index}"), user, f"model_{index}", 1, now=1000.1,
        )["allowed"]

    try:
        with ThreadPoolExecutor(max_workers=20) as pool:
            decisions = list(pool.map(attempt, range(100)))
        assert sum(decisions) == 10
    finally:
        keys = list(client.scan_iter(match=prefix + "*"))
        if keys:
            client.delete(*keys)


def test_rejects_negative_rate_limit_config():
    with pytest.raises(ValidationError):
        ApiKeyCreate(name="bad", project_id="project_test", qps_limit=-1)

    with pytest.raises(ValidationError):
        ApiKeyUpdate(rpm_limit=-1)

    with pytest.raises(ValidationError):
        AdminUserCreate(username="bad", email="bad@example.com", password="password", qps_limit=-1)

    with pytest.raises(ValidationError):
        AdminUserUpdate(concurrency_limit=-1)


def test_web_chat_uses_user_limits_without_key():
    redis = FakeRedis()
    user = _user(qps_limit=1, concurrency_limit=2)
    first = check_proxy_rate_limit(redis, None, user, 'gpt', 1, now=1000.1)
    assert first['allowed'] is True
    second = check_proxy_rate_limit(redis, None, user, 'other-model', 1, now=1000.2)
    assert second['allowed'] is False
    assert second['reason'] == 'user_qps_limit'
    release_proxy_concurrency(redis, first['concurrency_key'])
    assert redis.values['rl:concurrency:user:usr_1'] == 0
