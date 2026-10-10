import json
from types import SimpleNamespace

import httpx

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from app.api.v1 import proxy
from app.models.channel import ChannelType
from app.models.user import UserRole
from app.services import rate_limit_service


class FakeProxyService:
    reservation_id = "reservation"

    def __init__(self):
        self.forwarded = None
        self.usage = None
        self.reservation_released = False

    def check_model_group_access(self, api_key, user, model):
        return {"allowed": True}

    def reserve_quota(self, user, api_key, model, data):
        return self.reservation_id

    def forward_protocol_with_failover(self, *args):
        self.forwarded = args
        return {"success": True, "status_code": 200, "body": b'{"ok":true}',
                "content_type": "application/json", "channel_id": "channel", "latency_ms": 4}

    def select_candidates(self, *args):
        channel = SimpleNamespace(
            channel_id="channel", type=ChannelType.openai, upstream_format="responses",
            auth_type="bearer", auth_headers=None, endpoint="https://example.invalid", timeout=5,
        )
        return [(channel, SimpleNamespace(upstream_model="upstream"), "upstream-key")]

    def calculate_tokens(self, request_data, response_data):
        return response_data["usage"]

    def record_usage(self, *args, **kwargs):
        self.usage = (args, kwargs)

    async def deduct_quota(self, user, api_key, tokens):
        pass

    def release_reservation(self):
        self.reservation_released = True


@pytest.mark.parametrize(("path", "api_type", "payload"), [
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


@pytest.fixture
def responses_client(monkeypatch):
    service = FakeProxyService()
    calls, released = [], []
    state = {"raise_upstream": False}
    monkeypatch.setattr("app.services.proxy_service.create_proxy_service", lambda db: service)
    monkeypatch.setattr(rate_limit_service, "get_rate_limit_redis_client", lambda: object())
    monkeypatch.setattr(rate_limit_service, "check_proxy_rate_limit", lambda *args: {
        "allowed": True, "concurrency_key": ["key-concurrency", "user-concurrency"],
    })
    monkeypatch.setattr(rate_limit_service, "release_proxy_concurrency",
                        lambda redis, keys: released.extend(keys))
    monkeypatch.setattr("app.services.api_key_freeze_service.record_api_key_error", lambda *args: None)

    def upstream(request):
        calls.append((request.url.path, json.loads(request.content)))
        if state["raise_upstream"]:
            raise RuntimeError("upstream failed")
        return httpx.Response(200, json={
            "id": "resp_test", "object": "response", "status": "completed", "output": [],
            "usage": {"input_tokens": 2, "output_tokens": 3, "total_tokens": 5},
        })

    real_client = httpx.Client
    monkeypatch.setattr("app.services.conversation_gateway.httpx.Client",
                        lambda **kw: real_client(transport=httpx.MockTransport(upstream), **kw))
    app = FastAPI()
    app.include_router(proxy.router)
    app.dependency_overrides[proxy.get_db] = lambda: object()

    @app.middleware("http")
    async def auth_state(request, call_next):
        request.state.user = SimpleNamespace(user_id="user", role=UserRole.user)
        request.state.api_key = SimpleNamespace(key_id="key", user_id="user")
        request.state.request_id = "request"
        return await call_next(request)

    return TestClient(app, raise_server_exceptions=False), service, calls, released, state


def test_responses_endpoint_proxies_success(responses_client):
    client, service, calls, released, _ = responses_client
    response = client.post("/responses", json={"model": "m", "input": "hello"})
    assert response.status_code == 200, response.text
    assert response.json()["id"] == "resp_test"
    assert response.json()["usage"]["total_tokens"] == 5
    assert calls == [("/v1/responses", {"model": "upstream", "input": "hello"})]
    assert service.usage[0][4] == {"prompt_tokens": 2, "completion_tokens": 3, "total_tokens": 5}
    assert service.usage[1]["api_type"] == "responses"
    assert released == ["key-concurrency", "user-concurrency"]


def test_protocol_rate_limit_returns_retry_after(responses_client, monkeypatch):
    client, _, calls, _, _ = responses_client
    monkeypatch.setattr(rate_limit_service, "check_proxy_rate_limit", lambda *args: {
        "allowed": False, "detail": "用户级 QPS 已超过限制", "retry_after_ms": 1200,
    })
    response = client.post("/responses", json={"model": "m", "input": "hello"})
    assert response.status_code == 429
    assert response.json()["detail"] == "用户级 QPS 已超过限制"
    assert response.headers["retry-after"] == "2"
    assert calls == []


def test_protocol_upstream_exception_releases_both_concurrency_limits(responses_client):
    client, service, _, released, state = responses_client
    state["raise_upstream"] = True
    response = client.post("/responses", json={"model": "m", "input": "hello"})
    assert response.status_code == 500
    assert service.reservation_released
    assert released == ["key-concurrency", "user-concurrency"]


def test_candidate_selection_exception_releases_quota_and_concurrency(responses_client):
    client, service, _, released, _ = responses_client

    def fail_selection(*args):
        raise RuntimeError("selection failed")

    service.select_candidates = fail_selection
    response = client.post("/responses", json={"model": "m", "input": "hello"})
    assert response.status_code == 500
    assert service.reservation_released
    assert released == ["key-concurrency", "user-concurrency"]
