import time
from types import SimpleNamespace

import pytest
from pydantic import ValidationError

from app.schemas.api_key import ApiKeyCreate, ApiKeyUpdate
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


def _api_key(**limits):
    defaults = {
        "user_id": "usr_1",
        "key_id": "key_1",
        "qps_limit": 0,
        "rpm_limit": 0,
        "tpm_limit": 0,
        "concurrency_limit": 0,
    }
    defaults.update(limits)
    return SimpleNamespace(**defaults)


def test_allows_when_limits_are_empty():
    decision = check_proxy_rate_limit(FakeRedis(), _api_key(), "gpt", 100, now=1000.0)

    assert decision["allowed"] is True


def test_blocks_qps_limit():
    redis = FakeRedis()
    key = _api_key(qps_limit=1)

    assert check_proxy_rate_limit(redis, key, "gpt", 1, now=1000.1)["allowed"] is True
    decision = check_proxy_rate_limit(redis, key, "gpt", 1, now=1000.2)

    assert decision["allowed"] is False
    assert decision["reason"] == "qps_limit"
    assert decision["retry_after_ms"] > 0


def test_blocks_rpm_limit():
    redis = FakeRedis()
    key = _api_key(rpm_limit=1)

    assert check_proxy_rate_limit(redis, key, "gpt", 1, now=1000.0)["allowed"] is True
    decision = check_proxy_rate_limit(redis, key, "gpt", 1, now=1001.0)

    assert decision["allowed"] is False
    assert decision["reason"] == "rpm_limit"


def test_blocks_tpm_limit():
    redis = FakeRedis()
    key = _api_key(tpm_limit=100)

    assert check_proxy_rate_limit(redis, key, "gpt", 60, now=1000.0)["allowed"] is True
    decision = check_proxy_rate_limit(redis, key, "gpt", 50, now=1001.0)

    assert decision["allowed"] is False
    assert decision["reason"] == "tpm_limit"


def test_blocks_and_releases_concurrency_limit():
    redis = FakeRedis()
    key = _api_key(concurrency_limit=1)

    first = check_proxy_rate_limit(redis, key, "gpt", 1, now=1000.0)
    second = check_proxy_rate_limit(redis, key, "gpt", 1, now=1000.1)
    release_proxy_concurrency(redis, first["concurrency_key"])
    third = check_proxy_rate_limit(redis, key, "gpt", 1, now=1000.2)

    assert first["allowed"] is True
    assert second["allowed"] is False
    assert second["reason"] == "concurrency_limit"
    assert third["allowed"] is True


def test_rejects_negative_rate_limit_config():
    with pytest.raises(ValidationError):
        ApiKeyCreate(name="bad", project_id="project_test", qps_limit=-1)

    with pytest.raises(ValidationError):
        ApiKeyUpdate(rpm_limit=-1)
