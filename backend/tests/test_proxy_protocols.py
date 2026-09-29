from types import SimpleNamespace

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from app.api.v1 import proxy


class FakeProxyService:
    reservation_id = "reservation"

    def __init__(self):
        self.forwarded = None
        self.usage = None

    def check_model_group_access(self, api_key, user, model):
        return {"allowed": True}

    def reserve_quota(self, user, api_key, model, data):
        return self.reservation_id

    def forward_protocol_with_failover(self, *args):
        self.forwarded = args
        return {"success": True, "status_code": 200, "body": b'{"ok":true}',
                "content_type": "application/json", "channel_id": "channel", "latency_ms": 4}

    def calculate_tokens(self, request_data, response_data):
        return {"prompt_tokens": 0, "completion_tokens": 0, "total_tokens": 0}

    def record_usage(self, *args, **kwargs):
        self.usage = (args, kwargs)

    async def deduct_quota(self, user, api_key, tokens):
        pass

    def release_reservation(self):
        pass


@pytest.mark.parametrize(("path", "api_type", "payload"), [
    ("/responses", "responses", {"model": "m", "input": "hello"}),
    ("/embeddings", "embeddings", {"model": "m", "input": "hello"}),
    ("/images/generations", "images", {"model": "m", "prompt": "hello"}),
    ("/audio/transcriptions", "audio/transcriptions", None),
])
def test_protocol_endpoint_proxies_success(path, api_type, payload, monkeypatch):
    service = FakeProxyService()
    monkeypatch.setattr(proxy, "create_proxy_service", lambda db: service)
    monkeypatch.setattr(proxy, "get_rate_limit_redis_client", lambda: object())
    monkeypatch.setattr(proxy, "check_proxy_rate_limit", lambda *args: {"allowed": True, "concurrency_key": "c"})
    monkeypatch.setattr(proxy, "release_proxy_concurrency", lambda *args: None)

    app = FastAPI()
    app.include_router(proxy.router)
    app.dependency_overrides[proxy.get_db] = lambda: object()

    @app.middleware("http")
    async def auth_state(request, call_next):
        request.state.user = SimpleNamespace(user_id="user")
        request.state.api_key = SimpleNamespace(key_id="key")
        request.state.request_id = "request"
        return await call_next(request)

    if payload is None:
        response = TestClient(app).post(path, data={"model": "m", "response_format": "json"},
                                        files={"file": ("audio.mp3", b"audio", "audio/mpeg")})
    else:
        response = TestClient(app).post(path, json=payload)

    assert response.status_code == 200
    assert response.json() == {"ok": True}
    assert service.forwarded[3:5] == (api_type, {
        "responses": "responses", "embeddings": "embeddings",
        "images": "images/generations", "audio/transcriptions": "audio/transcriptions",
    }[api_type])
    assert service.usage[1]["api_type"] == api_type


def test_protocol_rate_limit_returns_retry_after(monkeypatch):
    monkeypatch.setattr(proxy, "create_proxy_service", lambda db: FakeProxyService())
    monkeypatch.setattr(proxy, "get_rate_limit_redis_client", lambda: object())
    monkeypatch.setattr(proxy, "check_proxy_rate_limit", lambda *args: {
        "allowed": False, "detail": "用户级 QPS 已超过限制", "retry_after_ms": 1200,
    })
    monkeypatch.setattr(proxy, "record_api_key_error", lambda *args: None)

    app = FastAPI()
    app.include_router(proxy.router)
    app.dependency_overrides[proxy.get_db] = lambda: object()

    @app.middleware("http")
    async def auth_state(request, call_next):
        request.state.user = SimpleNamespace(user_id="user")
        request.state.api_key = SimpleNamespace(key_id="key", user_id="user")
        request.state.request_id = "request"
        return await call_next(request)

    response = TestClient(app).post("/responses", json={"model": "m", "input": "hello"})

    assert response.status_code == 429
    assert response.json()["detail"] == "用户级 QPS 已超过限制"
    assert response.headers["retry-after"] == "2"


def test_protocol_upstream_exception_releases_both_concurrency_limits(monkeypatch):
    service = FakeProxyService()
    def fail_upstream(*args):
        raise RuntimeError("upstream failed")

    service.forward_protocol_with_failover = fail_upstream
    released = []
    monkeypatch.setattr(proxy, "create_proxy_service", lambda db: service)
    monkeypatch.setattr(proxy, "get_rate_limit_redis_client", lambda: object())
    monkeypatch.setattr(proxy, "check_proxy_rate_limit", lambda *args: {
        "allowed": True, "concurrency_key": ["key-concurrency", "user-concurrency"],
    })
    monkeypatch.setattr(proxy, "release_proxy_concurrency", lambda redis, keys: released.extend(keys))

    app = FastAPI()
    app.include_router(proxy.router)
    app.dependency_overrides[proxy.get_db] = lambda: object()

    @app.middleware("http")
    async def auth_state(request, call_next):
        request.state.user = SimpleNamespace(user_id="user")
        request.state.api_key = SimpleNamespace(key_id="key", user_id="user")
        request.state.request_id = "request"
        return await call_next(request)

    response = TestClient(app, raise_server_exceptions=False).post(
        "/responses", json={"model": "m", "input": "hello"},
    )

    assert response.status_code == 500
    assert released == ["key-concurrency", "user-concurrency"]
