import json
from types import SimpleNamespace

from fastapi import FastAPI
from fastapi.testclient import TestClient

import app.middleware as proxy_middleware
from app.middleware import ProxyAuthMiddleware
from app.models.api_key import ApiKey
from app.services.proxy_service import ProxyService


def test_api_key_ip_whitelist_allows_empty_config():
    api_key = SimpleNamespace(ip_whitelist=None)

    assert ProxyService.check_api_key_ip(api_key, "203.0.113.10") is True


def test_api_key_ip_whitelist_allows_exact_ip():
    api_key = SimpleNamespace(ip_whitelist=json.dumps(["203.0.113.10"]))

    assert ProxyService.check_api_key_ip(api_key, "203.0.113.10") is True


def test_api_key_ip_whitelist_allows_cidr():
    api_key = SimpleNamespace(ip_whitelist=json.dumps(["10.0.0.0/8"]))

    assert ProxyService.check_api_key_ip(api_key, "10.2.3.4") is True


def test_api_key_ip_whitelist_rejects_unmatched_ip():
    api_key = SimpleNamespace(ip_whitelist=json.dumps(["203.0.113.10", "10.0.0.0/8"]))

    assert ProxyService.check_api_key_ip(api_key, "198.51.100.8") is False


def test_api_key_ip_whitelist_ignores_invalid_entries_without_allowing_all():
    api_key = SimpleNamespace(ip_whitelist=json.dumps(["not-an-ip"]))

    assert ProxyService.check_api_key_ip(api_key, "198.51.100.8") is False


def test_proxy_middleware_rejects_ip_outside_whitelist(monkeypatch):
    api_key = SimpleNamespace(api_key="tmk_test", ip_whitelist=json.dumps(["203.0.113.10"]))
    user = SimpleNamespace(user_id="usr_test")
    app = _proxy_app(monkeypatch, api_key, user)

    response = TestClient(app).get(
        "/api/v1/proxy/ping",
        headers={
            "Authorization": "Bearer tmk_test",
            "X-Forwarded-For": "198.51.100.8",
        },
    )

    assert response.status_code == 403
    assert response.json()["detail"] == "IP不在API Key白名单内"


def test_proxy_middleware_allows_ip_inside_whitelist(monkeypatch):
    api_key = SimpleNamespace(api_key="tmk_test", ip_whitelist=json.dumps(["203.0.113.10"]))
    user = SimpleNamespace(user_id="usr_test")
    app = _proxy_app(monkeypatch, api_key, user)

    response = TestClient(app).get(
        "/api/v1/proxy/ping",
        headers={
            "Authorization": "Bearer tmk_test",
            "X-Forwarded-For": "203.0.113.10",
        },
    )

    assert response.status_code == 200
    assert response.json() == {"ok": True}


def _proxy_app(monkeypatch, api_key, user):
    class FakeDb:
        def close(self):
            pass

    class FakeProxyService:
        def __init__(self, db):
            self.db = db

        def verify_api_key(self, value):
            return api_key if value == api_key.api_key else None

        def get_user_from_key(self, key):
            return user

        def check_api_key_ip(self, key, client_ip):
            return ProxyService.check_api_key_ip(key, client_ip)

    monkeypatch.setattr(proxy_middleware, "SessionLocal", lambda: FakeDb())
    monkeypatch.setattr(proxy_middleware, "ProxyService", FakeProxyService)

    app = FastAPI()
    app.add_middleware(ProxyAuthMiddleware)

    @app.get("/api/v1/proxy/ping")
    async def ping():
        return {"ok": True}

    return app
