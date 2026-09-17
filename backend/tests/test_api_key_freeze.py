"""自动冻结的阈值、恢复权限和真实认证链路。"""
import asyncio
import json
from datetime import datetime

import pytest
from fastapi import FastAPI, HTTPException
from fastapi.testclient import TestClient
from sqlalchemy import BigInteger, create_engine
from sqlalchemy.ext.compiler import compiles
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

import app.models
import app.middleware as middleware
from app.core.database import Base
from app.models.api_key import ApiKey, ApiKeyStatus
from app.models.notification import Notification
from app.models.user import User, UserRole
from app.services.proxy_service import ProxyService


def _run(coroutine):
    # 不改变其他测试依赖的默认事件循环。
    loop = asyncio.new_event_loop()
    try:
        return loop.run_until_complete(coroutine)
    finally:
        loop.close()


@compiles(BigInteger, 'sqlite')
def sqlite_bigint(element, compiler, **kw):
    return 'INTEGER'


@pytest.fixture
def session():
    engine = create_engine('sqlite://', connect_args={'check_same_thread': False}, poolclass=StaticPool)
    Base.metadata.create_all(engine)
    db = sessionmaker(bind=engine)()
    db.add_all([
        User(user_id='owner', username='owner', email='owner@test.local', password='hash'),
        User(user_id='admin', username='admin', email='admin@test.local', password='hash', role=UserRole.admin),
        ApiKey(key_id='key_test', user_id='owner', api_key='tmk_test', key_name='test',
               ip_whitelist=json.dumps(['203.0.113.10']), status=ApiKeyStatus.active),
    ])
    db.commit()
    yield db
    db.close()
    engine.dispose()


@pytest.fixture
def redis_client():
    # 真实 Redis，独立随机前缀；不触碰业务计数器。
    import uuid
    from app.services.rate_limit_service import get_rate_limit_redis_client
    client = get_rate_limit_redis_client()
    prefix = 'test-freeze:' + uuid.uuid4().hex + ':'

    class ScopedRedis:
        def eval(self, script, numkeys, *args):
            return client.eval(script, numkeys, *[prefix + key for key in args[:numkeys]], *args[numkeys:])

        def zcard(self, key):
            return client.zcard(prefix + key)

        def hgetall(self, key):
            return client.hgetall(prefix + key)

        def delete(self, *keys):
            return client.delete(*[prefix + key for key in keys])

    yield ScopedRedis()
    keys = list(client.scan_iter(match=prefix + '*'))
    if keys:
        client.delete(*keys)


def record(db, redis, kind, now):
    from app.services.api_key_freeze_service import record_api_key_error
    return record_api_key_error(db, db.query(ApiKey).first(), kind, redis_client=redis, now=now)


def test_49_errors_allowed_50th_freezes_and_notifies_once(session, redis_client):
    for i in range(49):
        assert record(session, redis_client, 'ip_mismatch', 1000 + i / 10) is False
    assert session.query(ApiKey).first().status == ApiKeyStatus.active
    assert record(session, redis_client, 'auth', 1005) is True
    key = session.query(ApiKey).first()
    assert key.status == ApiKeyStatus.disabled
    assert key.frozen_at is not None
    assert key.frozen_reason
    assert '冻结' in ProxyService.get_api_key_auth_error(key)
    notifications = session.query(Notification).all()
    assert {n.user_id for n in notifications} == {'owner', 'admin'}
    assert all('tmk_test' not in (n.content + n.extra_data) for n in notifications)
    assert record(session, redis_client, 'ip_mismatch', 1006) is False
    assert session.query(Notification).count() == 2


def test_rolling_window_expires(session, redis_client):
    for i in range(49):
        record(session, redis_client, 'ip_mismatch', 1000)
    assert record(session, redis_client, 'ip_mismatch', 1060) is False
    assert session.query(ApiKey).first().status == ApiKeyStatus.active


@pytest.mark.parametrize('kind', ['quota', 'rate_limit', 'upstream_4xx'])
def test_non_security_errors_recorded_without_freezing(session, redis_client, kind):
    for i in range(55):
        assert record(session, redis_client, kind, 1000 + i / 100) is False
    assert session.query(ApiKey).first().status == ApiKeyStatus.active
    assert session.query(Notification).count() == 0


def test_middleware_freezes_ip_abuse_and_blocks_next_call(session, redis_client, monkeypatch):
    from app.services import api_key_freeze_service as service
    monkeypatch.setattr(service, 'get_rate_limit_redis_client', lambda: redis_client)
    factory = sessionmaker(bind=session.bind)
    monkeypatch.setattr(middleware, 'SessionLocal', factory)
    app = FastAPI()
    app.add_middleware(middleware.ProxyAuthMiddleware)

    @app.get('/api/v1/proxy/ping')
    def ping():
        return {'ok': True}

    with TestClient(app) as client:
        for i in range(50):
            response = client.get('/api/v1/proxy/ping', headers={'Authorization': 'Bearer tmk_test', 'X-Forwarded-For': '198.51.100.8'})
            assert response.status_code == 403
        response = client.get('/api/v1/proxy/ping', headers={'Authorization': 'Bearer tmk_test', 'X-Forwarded-For': '203.0.113.10'})
        assert response.status_code == 401
        assert '冻结' in response.json()['detail']
    session.expire_all()
    assert session.query(Notification).count() == 2


def test_owner_cannot_reenable_or_rotate_frozen_key(session):
    from app.api.v1.api_keys import update_api_key_status, rotate_api_key
    from app.schemas.api_key import ApiKeyStatusUpdate
    from starlette.requests import Request
    key = session.query(ApiKey).first()
    key.status = ApiKeyStatus.disabled
    key.frozen_at = datetime.utcnow()
    key.frozen_reason = 'abuse'
    session.commit()
    owner = session.query(User).filter(User.user_id == 'owner').first()
    request = Request({'type': 'http', 'headers': []})
    for action in [
        lambda: update_api_key_status(request, key.key_id, ApiKeyStatusUpdate(status='active'), owner, session),
        lambda: rotate_api_key(request, key.key_id, owner, session),
    ]:
        with pytest.raises(HTTPException) as exc:
            _run(action())
        assert exc.value.status_code == 403
    assert key.status == ApiKeyStatus.disabled


def test_admin_unfreeze_resets_counter_and_returns_freeze_metadata(session, redis_client, monkeypatch):
    from app.services import api_key_freeze_service as service
    from app.api.v1.api_keys import admin_unfreeze_api_key, _api_key_response
    from app.models.operation_log import OperationLog
    from starlette.requests import Request
    monkeypatch.setattr(service, 'get_rate_limit_redis_client', lambda: redis_client)
    for i in range(50):
        record(session, redis_client, 'ip_mismatch', 1000)
    key = session.query(ApiKey).first()
    response = _api_key_response(key, admin=True)
    assert response.frozen_at and response.frozen_reason
    assert response.api_key != 'tmk_test'
    admin = session.query(User).filter(User.user_id == 'admin').first()
    _run(admin_unfreeze_api_key(Request({'type': 'http', 'headers': []}), key.key_id, admin, session))
    assert key.status == ApiKeyStatus.active
    assert key.frozen_at is None
    assert key.frozen_reason is None
    assert record(session, redis_client, 'ip_mismatch', 1001) is False
    assert session.query(OperationLog).filter(OperationLog.action == 'unfreeze').count() == 1


def test_unknown_key_cannot_freeze_another_key(session, redis_client, monkeypatch):
    from app.services import api_key_freeze_service as service
    monkeypatch.setattr(service, 'get_rate_limit_redis_client', lambda: redis_client)
    monkeypatch.setattr(middleware, 'SessionLocal', sessionmaker(bind=session.bind))
    app = FastAPI()
    app.add_middleware(middleware.ProxyAuthMiddleware)
    with TestClient(app) as client:
        for _ in range(55):
            assert client.get('/api/v1/proxy/ping', headers={'Authorization': 'Bearer unknown'}).status_code == 401
    assert session.query(ApiKey).first().status == ApiKeyStatus.active
    assert session.query(Notification).count() == 0


def test_known_expired_key_auth_errors_are_attributed(session, redis_client, monkeypatch):
    from app.services import api_key_freeze_service as service
    key = session.query(ApiKey).first()
    key.expires_at = datetime(2020, 1, 1)
    session.commit()
    monkeypatch.setattr(service, 'get_rate_limit_redis_client', lambda: redis_client)
    monkeypatch.setattr(middleware, 'SessionLocal', sessionmaker(bind=session.bind))
    app = FastAPI()
    app.add_middleware(middleware.ProxyAuthMiddleware)
    with TestClient(app) as client:
        for _ in range(50):
            assert client.get('/api/v1/proxy/ping', headers={'Authorization': 'Bearer tmk_test'}).status_code == 401
    session.expire_all()
    assert session.query(ApiKey).first().status == ApiKeyStatus.disabled
    assert session.query(Notification).count() == 2


def test_upstream_4xx_observed_even_when_failover_succeeds(session, redis_client, monkeypatch):
    from types import SimpleNamespace
    from app.services import api_key_freeze_service as service
    monkeypatch.setattr(service, 'get_rate_limit_redis_client', lambda: redis_client)
    proxy = ProxyService(session)
    key = session.query(ApiKey).first()
    user = session.query(User).filter(User.user_id == 'owner').first()
    candidates = [(SimpleNamespace(channel_id='one'), SimpleNamespace(upstream_model='gpt'), 'upstream'),
                  (SimpleNamespace(channel_id='two'), SimpleNamespace(upstream_model='gpt'), 'upstream')]
    monkeypatch.setattr(proxy, 'select_candidates', lambda *args: candidates)
    results = iter([{'success': False, 'status_code': 400}, {'success': True, 'status_code': 200, 'channel_id': 'two'}])
    monkeypatch.setattr(proxy, '_forward_one', lambda *args: next(results))
    assert proxy.forward_with_failover('gpt', user, key, {})['success'] is True
    assert redis_client.zcard(service._scope(key) + ':upstream_4xx') == 1
    assert redis_client.hgetall(service._scope(key) + ':streak') == {}
    assert key.status == ApiKeyStatus.active


def test_security_window_is_not_reset_by_success_and_isolates_other_keys(session, redis_client):
    from app.services.api_key_freeze_service import record_api_key_error, record_api_key_success
    key = session.query(ApiKey).first()
    other = ApiKey(key_id='key_other', user_id='owner', api_key='tmk_other', key_name='other')
    session.add(other)
    session.commit()
    for _ in range(49):
        record_api_key_error(session, key, 'ip_mismatch', redis_client, now=1000)
    record_api_key_success(key, redis_client)
    assert record_api_key_error(session, other, 'ip_mismatch', redis_client, now=1001) is False
    assert record_api_key_error(session, key, 'auth', redis_client, now=1001) is True
    assert session.query(ApiKey).filter(ApiKey.key_id == 'key_other').first().status == ApiKeyStatus.active


def test_freeze_migration_upgrade_and_downgrade():
    import importlib.util
    from pathlib import Path
    from alembic.migration import MigrationContext
    from alembic.operations import Operations
    from sqlalchemy import inspect, text
    path = Path(__file__).parents[1] / 'alembic/versions/20260915_1200_api_key_freeze.py'
    spec = importlib.util.spec_from_file_location('freeze_migration', path)
    migration = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(migration)
    engine = create_engine('sqlite://')
    with engine.begin() as connection:
        connection.execute(text('CREATE TABLE api_keys (id INTEGER PRIMARY KEY)'))
        migration.op = Operations(MigrationContext.configure(connection))
        migration.upgrade()
        assert {c['name'] for c in inspect(connection).get_columns('api_keys')} == {'id', 'frozen_at', 'frozen_reason', 'frozen_until'}
        migration.downgrade()
        assert [c['name'] for c in inspect(connection).get_columns('api_keys')] == ['id']
    engine.dispose()


@pytest.mark.parametrize('kind', ['quota', 'rate_limit'])
def test_proxy_rejections_are_counted(session, redis_client, monkeypatch, kind):
    from app.api.v1 import proxy as api
    from app.services import api_key_freeze_service as service
    from starlette.requests import Request
    monkeypatch.setattr(service, 'get_rate_limit_redis_client', lambda: redis_client)
    monkeypatch.setattr(api, 'get_rate_limit_redis_client', lambda: redis_client)
    proxy = ProxyService(session)
    monkeypatch.setattr(api, 'create_proxy_service', lambda db: proxy)
    monkeypatch.setattr(proxy, 'check_model_group_access', lambda *args: {'allowed': True})
    if kind == 'rate_limit':
        monkeypatch.setattr(proxy, 'check_quota', lambda *args: {'allowed': True})
        monkeypatch.setattr(api, 'check_proxy_rate_limit', lambda *args: {'allowed': False, 'retry_after_ms': 1500})
    request = Request({'type': 'http', 'headers': []})
    key = session.query(ApiKey).first()
    request.state.api_key = key
    request.state.user = session.query(User).filter(User.user_id == 'owner').first()
    with pytest.raises(HTTPException) as exc:
        _run(api.chat_completions(request, api.ChatCompletionRequest(model='gpt', messages=[]), session))
    assert exc.value.status_code == (403 if kind == 'quota' else 429)
    assert redis_client.zcard(service._scope(key) + ':' + kind) == 1
    assert key.status == ApiKeyStatus.active


def test_stream_upstream_4xx_is_counted(session, redis_client, monkeypatch):
    import httpx
    from types import SimpleNamespace
    from app.models.channel import ChannelType
    from app.services import api_key_freeze_service as service
    import app.services.proxy_service as module
    monkeypatch.setattr(service, 'get_rate_limit_redis_client', lambda: redis_client)
    proxy = ProxyService(session)
    key = session.query(ApiKey).first()
    user = session.query(User).filter(User.user_id == 'owner').first()
    channel = SimpleNamespace(timeout=1, upstream_format='chat', type=ChannelType.openai,
                              auth_type='bearer', auth_headers=None, endpoint='https://upstream.test')
    monkeypatch.setattr(proxy, 'select_channel', lambda *args: (channel, 'gpt', 'upstream'))
    real_client = httpx.Client
    transport = httpx.MockTransport(lambda request: httpx.Response(400, json={'error': {'message': 'invalid request'}}))
    monkeypatch.setattr(module.httpx, 'Client', lambda **kw: real_client(transport=transport, **kw))
    chunks = list(proxy.forward_stream('gpt', user, key, {}))
    assert any('invalid request' in chunk for chunk in chunks)
    assert redis_client.zcard(service._scope(key) + ':upstream_4xx') == 1
    assert key.status == ApiKeyStatus.active


def test_redis_failure_preserves_key_status(session):
    class BrokenRedis:
        def eval(self, *args):
            raise ConnectionError('unavailable')
    assert record(session, BrokenRedis(), 'ip_mismatch', 1000) is False
    assert session.query(ApiKey).first().status == ApiKeyStatus.active


def test_freeze_marker_blocks_even_if_status_is_active():
    from types import SimpleNamespace
    key = SimpleNamespace(status='active', revoked_at=None, frozen_at=datetime.utcnow(),
                          frozen_reason='abuse', expires_at=None)
    assert '冻结' in (ProxyService.get_api_key_auth_error(key) or '')


def test_stale_worker_cannot_duplicate_freeze_notifications(session, redis_client):
    from app.services.api_key_freeze_service import record_api_key_error
    worker = sessionmaker(bind=session.bind)()
    stale_key = worker.query(ApiKey).first()
    assert stale_key.frozen_at is None
    try:
        for _ in range(50):
            record(session, redis_client, 'ip_mismatch', 1000)
        assert record_api_key_error(worker, stale_key, 'ip_mismatch', redis_client, now=1001) is False
        assert session.query(Notification).count() == 2
    finally:
        worker.close()


def test_unfreeze_http_requires_admin_and_preserves_revocation(session, redis_client, monkeypatch):
    from app.api.v1.api_keys import router
    from app.dependencies import get_current_user
    from app.core.database import get_db
    from app.services import api_key_freeze_service as service
    monkeypatch.setattr(service, 'get_rate_limit_redis_client', lambda: redis_client)
    for _ in range(50):
        record(session, redis_client, 'ip_mismatch', 1000)
    app = FastAPI()
    app.include_router(router, prefix='/api-keys')
    app.dependency_overrides[get_db] = lambda: session
    app.dependency_overrides[get_current_user] = lambda: session.query(User).filter(User.user_id == 'owner').first()
    with TestClient(app) as client:
        assert client.put('/api-keys/admin/key_test/unfreeze').status_code == 403
        app.dependency_overrides[get_current_user] = lambda: session.query(User).filter(User.user_id == 'admin').first()
        key = session.query(ApiKey).first()
        key.status = ApiKeyStatus.revoked
        key.revoked_at = datetime.utcnow()
        session.commit()
        assert client.put('/api-keys/admin/key_test/unfreeze').status_code == 400
        assert key.status == ApiKeyStatus.revoked
