"""Task 2.1: 项目权限、用量快照和历史统计兼容。"""
from decimal import Decimal

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from sqlalchemy import BigInteger, create_engine
from sqlalchemy.ext.compiler import compiles
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

import app.models
from app.core.database import Base, get_db
from app.dependencies import get_current_user, require_admin
from app.models.user import User, UserRole
from app.models.api_key import ApiKey
from app.models.model import Model
from app.models.usage_log import UsageLog
from app.services.proxy_service import ProxyService
from app.api.v1 import api_keys, admin, stats


@compiles(BigInteger, 'sqlite')
def sqlite_bigint(element, compiler, **kw):
    return 'INTEGER'


@pytest.fixture
def ctx():
    engine = create_engine('sqlite://', connect_args={'check_same_thread': False}, poolclass=StaticPool)
    Base.metadata.create_all(engine)
    db = sessionmaker(bind=engine)()
    owner = User(user_id='owner', username='owner', email='owner@test', password='hash')
    administrator = User(user_id='admin', username='admin', email='admin@test', password='hash', role=UserRole.admin)
    db.add_all([owner, administrator])
    db.commit()
    app = FastAPI()
    app.include_router(api_keys.router, prefix='/keys')
    app.include_router(admin.router, prefix='/admin')
    app.include_router(stats.router, prefix='/stats')
    import importlib.util
    if importlib.util.find_spec('app.api.v1.projects'):
        from app.api.v1 import projects
        app.include_router(projects.router, prefix='/projects')
    app.dependency_overrides[get_db] = lambda: db
    app.dependency_overrides[get_current_user] = lambda: owner
    app.dependency_overrides[require_admin] = lambda: administrator
    with TestClient(app) as client:
        yield db, client
    db.close()
    engine.dispose()


def setup_project(client, name='项目', user_ids=None):
    response = client.post('/projects/admin/departments', json={'name': '研发部'})
    assert response.status_code == 200, response.text
    dep = response.json()
    resp = client.post('/projects/admin', json={'name': name, 'dept_id': dep['dept_id']})
    assert resp.status_code == 200, resp.text
    project = resp.json()
    if user_ids is not None:
        resp = client.put(f"/projects/admin/{project['project_id']}/users", json={'user_ids': user_ids})
        assert resp.status_code == 200, resp.text
    return project


def test_key_creation_requires_authorized_active_project(ctx):
    db, client = ctx
    assert client.post('/keys', json={'name': 'missing'}).status_code == 422
    project = setup_project(client)
    payload = {'name': 'key', 'project_id': project['project_id']}
    assert client.post('/keys', json=payload).status_code == 403
    client.put(f"/projects/admin/{project['project_id']}/users", json={'user_ids': ['owner']})
    result = client.post('/keys', json=payload)
    assert result.status_code == 200, result.text
    assert result.json()['project_id'] == project['project_id']
    assert client.get('/projects').json()['items'][0]['project_id'] == project['project_id']
    client.put(f"/projects/admin/{project['project_id']}", json={'name': '项目', 'dept_id': project['dept_id'], 'status': 'disabled'})
    assert client.post('/keys', json=payload).status_code == 403


def test_update_rejects_clear_and_unassigned_project_rotate_preserves(ctx):
    db, client = ctx
    p1 = setup_project(client, user_ids=['owner'])
    p2 = setup_project(client)
    key = client.post('/keys', json={'name': 'key', 'project_id': p1['project_id']}).json()
    key_id = key['key_id']
    assert client.put(f'/keys/{key_id}', json={'project_id': None}).status_code == 422
    assert client.put(f'/keys/admin/{key_id}', json={'project_id': p2['project_id']}).status_code == 403
    result = client.post(f'/keys/{key_id}/rotate')
    assert result.status_code == 200, result.text
    assert result.json()['project_id'] == p1['project_id']
    assert client.get('/keys').json()['items'][0]['project_id'] == p1['project_id']
    assert client.put(f"/projects/admin/{p1['project_id']}/users", json={'user_ids': ['missing']}).status_code == 404
    assert client.get(f"/projects/admin/{p1['project_id']}/users").json()['user_ids'] == ['owner']


def test_usage_snapshots_cost_department_and_failure_zero(ctx):
    db, client = ctx
    project = setup_project(client, user_ids=['owner'])
    key = client.post('/keys', json={'name': 'key', 'project_id': project['project_id']}).json()
    db.add(Model(model_id='model', price_per_1k_input=Decimal('1'), price_per_1k_output=Decimal('2')))
    db.commit()
    service = ProxyService(db)
    service.record_usage('owner', key['key_id'], 'channel', 'model', {'prompt_tokens': 100, 'completion_tokens': 50, 'total_tokens': 150}, 10, 200)
    db.commit()
    row = db.query(UsageLog).one()
    assert row.project_id == project['project_id']
    assert row.department_id == project['dept_id']
    assert row.cost_usd == Decimal('0.2')
    db.query(Model).one().price_per_1k_input = Decimal('100')
    other_dep = client.post('/projects/admin/departments', json={'name': '其他部'}).json()
    client.put(f"/projects/admin/{project['project_id']}", json={'name': '调整项目', 'dept_id': other_dep['dept_id']})
    db.refresh(row)
    assert row.department_id == project['dept_id']
    assert row.cost_usd == Decimal('0.2')
    ProxyService(db)._record_usage_failure('owner', key['key_id'], 'channel', 'model', 502, 'failed')
    failed = db.query(UsageLog).filter(UsageLog.status_code == 502).one()
    assert failed.project_id == project['project_id']
    assert failed.department_id == other_dep['dept_id']
    assert failed.cost_usd == 0


def test_admin_project_filter_applies_to_all_stats_and_keeps_legacy(ctx):
    db, client = ctx
    project = setup_project(client)
    db.add_all([
        UsageLog(log_id='new', user_id='owner', key_id='key', channel_id='channel', model='model', project_id=project['project_id'], department_id=project['dept_id'], cost_usd=Decimal('0.25'), total_tokens=100, status_code=200),
        UsageLog(log_id='old', user_id='owner', key_id='old', model='legacy', total_tokens=10, status_code=500),
    ])
    db.commit()
    filtered = client.get('/admin/stats/usage', params={'project_id': project['project_id']}).json()
    assert filtered['total_requests'] == 1
    assert filtered['total_tokens'] == 100
    assert filtered['success_rate'] == 100
    assert sum(x['requests'] for x in filtered['by_day']) == 1
    assert sum(x['requests'] for x in filtered['by_user']) == 1
    assert filtered['by_model'][0]['cost'] == 0.25
    all_stats = client.get('/admin/stats/usage').json()
    assert all_stats['total_requests'] == 2
    assert db.query(UsageLog).filter_by(log_id='old').one().project_id is None


def test_real_upstream_usage_tokens_take_precedence(ctx):
    db, client = ctx
    tokens = ProxyService(db).calculate_tokens({'messages': [{'content': '估算不应覆盖真实用量'}]},
        {'usage': {'prompt_tokens': 123, 'completion_tokens': 45, 'total_tokens': 168}})
    assert tokens == {'prompt_tokens': 123, 'completion_tokens': 45, 'total_tokens': 168}


@pytest.mark.parametrize('status', [200, 503])
def test_stream_metadata_keeps_channel_result_and_usage(ctx, monkeypatch, status):
    import httpx
    from app.models.channel import Channel, ChannelType
    db, client = ctx
    project = setup_project(client, user_ids=['owner'])
    key_data = client.post('/keys', json={'name': 'key', 'project_id': project['project_id']}).json()
    key = db.query(ApiKey).filter_by(key_id=key_data['key_id']).one()
    user = db.query(User).filter_by(user_id='owner').one()
    channel = Channel(channel_id='selected', name='selected', type=ChannelType.openai, endpoint='https://upstream.test', timeout=10, upstream_format='chat', auth_type='bearer')
    service = ProxyService(db)
    monkeypatch.setattr(service, 'select_channel', lambda *args: (channel, 'upstream', 'test-key'))
    real_client = httpx.Client
    body = ('data: {"choices":[{"delta":{"content":"hello"}}]}\n\n'
            'data: {"usage":{"prompt_tokens":123,"completion_tokens":45,"total_tokens":168}}\n\n'
            'data: [DONE]\n\n') if status == 200 else '{"error":{"message":"failed"}}'
    def handle(request):
        import json
        assert json.loads(request.content)['stream'] is True
        return httpx.Response(status, text=body)
    transport = httpx.MockTransport(handle)
    monkeypatch.setattr(httpx, 'Client', lambda **kw: real_client(transport=transport, **kw))
    chunks = list(service.forward_stream('platform', user, key, {'messages': [{'role': 'user', 'content': 'hello'}]}))
    assert chunks
    assert service.stream_metadata['channel_id'] == 'selected'
    assert service.stream_metadata['status_code'] == status
    if status == 200:
        assert service.stream_metadata['tokens']['total_tokens'] == 168
    else:
        assert service.stream_metadata['error'] == 'failed'


@pytest.mark.parametrize("precreated", [False, True])
def test_migration_backfills_keys_and_preserves_old_logs(monkeypatch, precreated):
    import importlib.util
    from pathlib import Path
    from alembic.migration import MigrationContext
    from alembic.operations import Operations
    from sqlalchemy import text, inspect
    path = Path(__file__).parents[1] / 'alembic/versions/20260917_1000_project_attribution.py'
    spec = importlib.util.spec_from_file_location('attribution_migration', path)
    migration = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(migration)
    engine = create_engine('sqlite://')
    with engine.begin() as connection:
        connection.execute(text('CREATE TABLE users (user_id VARCHAR(32) PRIMARY KEY)'))
        connection.execute(text('CREATE TABLE api_keys (key_id VARCHAR(64) PRIMARY KEY, user_id VARCHAR(32))'))
        connection.execute(text('CREATE TABLE usage_logs (log_id VARCHAR(50) PRIMARY KEY, total_tokens INTEGER)'))
        connection.execute(text("INSERT INTO users VALUES ('owner')"))
        connection.execute(text("INSERT INTO api_keys VALUES ('key', 'owner'), ('key2', 'owner')"))
        connection.execute(text("INSERT INTO usage_logs VALUES ('old', 100)"))
        monkeypatch.setattr(migration, 'op', Operations(MigrationContext.configure(connection)))
        if precreated:
            Base.metadata.tables['departments'].create(connection)
            Base.metadata.tables['projects'].create(connection)
            Base.metadata.tables['user_projects'].create(connection)
        migration.upgrade()
        assert connection.execute(text('SELECT DISTINCT project_id FROM api_keys')).scalars().all() == ['project_default']
        assert connection.execute(text('SELECT COUNT(*) FROM user_projects')).scalar() == 1
        assert connection.execute(text('SELECT project_id, department_id, cost_usd, total_tokens FROM usage_logs')).one() == (None, None, None, 100)
        migration.downgrade()
        assert 'projects' not in inspect(connection).get_table_names()
        assert connection.execute(text('SELECT total_tokens FROM usage_logs')).scalar() == 100
        migration.upgrade()
        assert connection.execute(text('SELECT COUNT(*) FROM user_projects')).scalar() == 1
    engine.dispose()


def test_request_attribution_stays_after_key_change(ctx):
    db, client = ctx
    p1 = setup_project(client, user_ids=['owner'])
    p2 = setup_project(client, user_ids=['owner'])
    key = client.post('/keys', json={'name': 'key', 'project_id': p1['project_id']}).json()
    service = ProxyService(db)
    service.capture_usage_attribution(key['key_id'])
    client.put(f"/keys/{key['key_id']}", json={'project_id': p2['project_id']})
    service.record_usage('owner', key['key_id'], 'channel', 'model', {}, 10, 200)
    db.commit()
    assert db.query(UsageLog).one().project_id == p1['project_id']


def test_failover_other_4xx_is_logged_with_attribution(ctx, monkeypatch):
    from types import SimpleNamespace
    import app.services.proxy_service as module
    db, client = ctx
    project = setup_project(client, user_ids=['owner'])
    key_data = client.post('/keys', json={'name': 'key', 'project_id': project['project_id']}).json()
    key = db.query(ApiKey).filter_by(key_id=key_data['key_id']).one()
    user = db.query(User).filter_by(user_id='owner').one()
    service = ProxyService(db)
    monkeypatch.setattr(service, 'select_candidates', lambda *args: [(SimpleNamespace(channel_id='selected'), SimpleNamespace(upstream_model='upstream'), 'test-key')])
    monkeypatch.setattr(service, '_forward_one', lambda *args: {'success': False, 'status_code': 422, 'channel_id': 'selected', 'error': 'invalid request'})
    monkeypatch.setattr(module, 'record_api_key_error', lambda *args: None)
    result = service.forward_with_failover('platform', user, key, {})
    assert result['status_code'] == 422
    assert db.query(UsageLog).count() == 1
    row = db.query(UsageLog).one()
    assert row.project_id == project['project_id']
    assert row.channel_id == 'selected'
    assert row.cost_usd == 0


def test_request_price_and_mixed_legacy_cost(ctx):
    from app.models.model import PriceType
    db, client = ctx
    project = setup_project(client, user_ids=['owner'])
    key = client.post('/keys', json={'name': 'key', 'project_id': project['project_id']}).json()
    db.add_all([
        Model(model_id='request', price_type=PriceType.request, price_per_request=Decimal('0.3')),
        Model(model_id='token', price_per_1k_input=Decimal('1'), price_per_1k_output=Decimal('2')),
        UsageLog(log_id='legacy', user_id='owner', key_id='old', model='token', prompt_tokens=100, completion_tokens=50, total_tokens=150, status_code=200),
        UsageLog(log_id='snapshot', user_id='owner', key_id='key', model='token', prompt_tokens=100, completion_tokens=50, total_tokens=150, status_code=200, cost_usd=Decimal('0.5')),
    ])
    db.commit()
    ProxyService(db).record_usage('owner', key['key_id'], 'channel', 'request', {}, 10, 200)
    db.commit()
    assert db.query(UsageLog).filter_by(model='request').one().cost_usd == Decimal('0.3')
    for path in ['/admin/stats/usage', '/stats/usage']:
        response = client.get(path)
        assert response.status_code == 200, response.text
        assert sum(row['cost'] for row in response.json()['by_model']) == pytest.approx(1)


def test_non_admin_cannot_manage_project_or_departments(ctx):
    db, client = ctx
    client.app.dependency_overrides.pop(require_admin)
    assert client.get('/projects/admin').status_code == 403
    assert client.post('/projects/admin/departments', json={'name': '部门'}).status_code == 403
    assert client.put('/projects/admin/unknown/users', json={'user_ids': ['owner']}).status_code == 403


@pytest.mark.parametrize('status', [200, 503])
def test_proxy_stream_route_persists_channel_attribution_and_cost(ctx, monkeypatch, status):
    import httpx
    import app.api.v1.proxy as proxy_module
    import app.core.database as database
    import app.services.proxy_service as service_module
    from app.models.channel import Channel, ChannelType
    db, client = ctx
    project = setup_project(client, user_ids=['owner'])
    key_data = client.post('/keys', json={'name': 'key', 'project_id': project['project_id']}).json()
    key = db.query(ApiKey).filter_by(key_id=key_data['key_id']).one()
    user = db.query(User).filter_by(user_id='owner').one()
    user.quota = -1
    db.add(Model(model_id='platform', price_per_1k_input=Decimal('1'), price_per_1k_output=Decimal('2')))
    db.commit()
    channel = Channel(channel_id='selected', name='selected', type=ChannelType.openai, endpoint='https://upstream.test', timeout=10, upstream_format='chat', auth_type='bearer')
    monkeypatch.setattr(ProxyService, 'select_channel', lambda *args: (channel, 'upstream', 'test-key'))
    monkeypatch.setattr(ProxyService, 'check_model_group_access', lambda *args: {'allowed': True})
    monkeypatch.setattr(proxy_module, 'get_rate_limit_redis_client', lambda: None)
    monkeypatch.setattr(proxy_module, 'check_proxy_rate_limit', lambda *args: {'allowed': True})
    monkeypatch.setattr(proxy_module, 'release_proxy_concurrency', lambda *args: None)
    monkeypatch.setattr(database, 'SessionLocal', sessionmaker(bind=db.get_bind()))
    body = ('data: {"choices":[{"delta":{"content":"hello"}}]}\n\n'
            'data: {"usage":{"prompt_tokens":100,"completion_tokens":50,"total_tokens":150}}\n\n'
            'data: [DONE]\n\n') if status == 200 else '{"error":{"message":"failed"}}'
    real_client = httpx.Client
    transport = httpx.MockTransport(lambda request: httpx.Response(status, text=body))
    monkeypatch.setattr(service_module.httpx, 'Client', lambda **kw: real_client(transport=transport, **kw))
    stream_app = FastAPI()
    stream_app.include_router(proxy_module.router, prefix='/proxy')
    stream_app.dependency_overrides[get_db] = lambda: db

    @stream_app.middleware('http')
    async def inject_auth(request, call_next):
        request.state.user = user
        request.state.api_key = key
        return await call_next(request)

    response = TestClient(stream_app).post('/proxy/chat/completions', json={'model': 'platform', 'stream': True, 'messages': [{'role': 'user', 'content': 'hello'}]})
    assert response.status_code == 200
    db.expire_all()
    rows = db.query(UsageLog).all()
    assert len(rows) == 1
    row = rows[0]
    assert row.model == 'platform'
    assert row.channel_id == 'selected'
    assert row.project_id == project['project_id']
    assert row.department_id == project['dept_id']
    assert row.status_code == status
    assert row.total_tokens == (150 if status == 200 else 0)
    assert row.cost_usd == (Decimal('0.2') if status == 200 else 0)
    assert db.query(User).filter_by(user_id='owner').one().quota_used == (150 if status == 200 else 0)
