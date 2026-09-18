"""真实 MySQL/Redis 验证账务状态和同用户并发准入。"""
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timedelta
from decimal import Decimal
import uuid

import pytest
from fastapi import HTTPException

from app.models.user import User
from app.models.api_key import ApiKey
from app.models.model import Model
from app.services.proxy_service import ProxyService


@pytest.fixture
def account(db):
    uid = uuid.uuid4().hex
    db.add_all([User(user_id=uid, username=uid, email=uid+'@test', password='hash', quota=200),
                ApiKey(key_id=uid, user_id=uid, api_key=uid, key_name='test'),
                Model(model_id='priced', price_per_1k_input=1, price_per_1k_output=2)])
    db.commit()
    return uid


def reserve(db, uid, output=100):
    service = ProxyService(db)
    user = db.query(User).filter_by(user_id=uid).one()
    key = db.query(ApiKey).filter_by(key_id=uid).one()
    return service.reserve_quota(user, key, 'priced', {'messages': [{'role': 'user', 'content': 'hi'}], 'max_tokens': output})


def test_twenty_parallel_requests_cannot_overdraw(db, account, SessionLocal):
    def attempt(_):
        with SessionLocal() as session:
            try:
                return reserve(session, account)
            except HTTPException as exc:
                assert exc.status_code == 403
                return None
    with ThreadPoolExecutor(max_workers=20) as pool:
        ids = [rid for rid in pool.map(attempt, range(20)) if rid]
    assert len(ids) == 1
    from app.services.quota_reservation_service import QuotaReservationService
    service = QuotaReservationService(db)
    for rid in ids:
        service.commit(rid, {'prompt_tokens': 2, 'completion_tokens': 40, 'total_tokens': 42})
        service.commit(rid, {'prompt_tokens': 2, 'completion_tokens': 40, 'total_tokens': 42})
    db.expire_all()
    assert db.query(User).filter_by(user_id=account).one().quota_used == 42


def test_actual_cost_release_and_expiry(db, account):
    from app.services.quota_reservation_service import QuotaReservationService
    from app.models.quota_reservation import QuotaReservation
    service = QuotaReservationService(db)
    rid = reserve(db, account)
    service.commit(rid, {'prompt_tokens': 2, 'completion_tokens': 40, 'total_tokens': 42})
    row = db.get(QuotaReservation, rid)
    assert row.status == 'committed'
    assert row.actual_cost_usd == Decimal('0.082')
    assert row.estimated_cost_usd >= row.actual_cost_usd
    service.release(rid)
    assert db.get(QuotaReservation, rid).status == 'committed'
    failed = reserve(db, account, 50)
    service.release(failed)
    service.release(failed)
    assert db.get(QuotaReservation, failed).status == 'released'
    expired = reserve(db, account, 50)
    db.get(QuotaReservation, expired).expires_at = datetime.utcnow() - timedelta(seconds=1)
    db.commit()
    service.expire()
    assert db.get(QuotaReservation, expired).status == 'expired'
    assert db.query(User).filter_by(user_id=account).one().quota_used == 42


@pytest.mark.parametrize('stream', [False, True])
@pytest.mark.parametrize('chat', [False, True])
@pytest.mark.parametrize('status', [200, 503])
def test_all_entrypoints_reserve_and_finish(db, account, SessionLocal, monkeypatch, stream, chat, status):
    import httpx
    from fastapi import FastAPI
    from fastapi.testclient import TestClient
    from app.core.database import get_db
    import app.core.database as database
    from app.dependencies import get_current_user
    from app.api.v1 import proxy, chat as chat_module
    from app.models.channel import Channel, ChannelType
    from app.models.chat import ChatConversation
    from app.models.usage_log import UsageLog
    user = db.query(User).filter_by(user_id=account).one()
    key = db.query(ApiKey).filter_by(key_id=account).one()
    channel = Channel(channel_id='selected', name='test', type=ChannelType.openai,
                      endpoint='https://test.invalid', timeout=10, upstream_format='chat', auth_type='bearer')
    monkeypatch.setattr(ProxyService, 'check_model_group_access', lambda *args: {'allowed': True})
    monkeypatch.setattr(ProxyService, 'select_channel', lambda *args: (channel, 'upstream', 'fake'))
    monkeypatch.setattr(ProxyService, 'select_candidates', lambda *args: [(channel, type('MC', (), {'upstream_model': 'upstream'})(), 'fake')])
    monkeypatch.setattr(chat_module, 'get_user_api_key', lambda *args: key)
    monkeypatch.setattr(database, 'SessionLocal', SessionLocal)
    observed = []
    occupied = []
    def upstream(request):
        import json
        observed.append(json.loads(request.content))
        with SessionLocal() as check:
            from app.models.quota_reservation import QuotaReservation
            occupied.append(check.query(QuotaReservation).filter_by(user_id=account, status='reserved').count())
        if status != 200:
            return httpx.Response(status, json={'error': {'message': 'failed'}})
        data = {'choices': [{'message': {'content': 'hello'}}], 'usage': {'prompt_tokens': 2, 'completion_tokens': 40, 'total_tokens': 42}}
        if stream:
            content = {'choices': [{'delta': {'content': 'hello'}}]}
            usage = {'choices': [], 'usage': data['usage']}
            return httpx.Response(200, text='data: '+json.dumps(content)+'\n\ndata: '+json.dumps(usage)+'\n\ndata: [DONE]\n\n')
        return httpx.Response(200, json=data)
    real_client = httpx.Client
    monkeypatch.setattr('app.services.proxy_service.httpx.Client', lambda **kw: real_client(transport=httpx.MockTransport(upstream), **kw))
    app = FastAPI()
    app.include_router(chat_module.router if chat else proxy.router, prefix='/api')
    app.dependency_overrides[get_db] = lambda: db
    app.dependency_overrides[get_current_user] = lambda: user
    @app.middleware('http')
    async def auth(request, call_next):
        request.state.user, request.state.api_key = user, key
        return await call_next(request)
    if chat:
        db.add(ChatConversation(conversation_id='conv', user_id=account, model_id='priced'))
        db.commit()
    payload = {'model': 'priced', 'messages': [{'role': 'user', 'content': 'hi'}], 'max_tokens': 100, 'stream': stream}
    response = TestClient(app).post('/api/conv/messages' if chat else '/api/chat/completions', json=payload)
    assert response.status_code == (200 if stream or status == 200 else 503), response.text
    assert observed and observed[0]['max_tokens'] == 100
    if stream:
        assert observed[0]['stream_options']['include_usage'] is True
    assert occupied == [1]
    db.rollback()  # 流式在独立 session 结算，结束 MySQL repeatable-read 快照。
    db.expire_all()
    from app.models.quota_reservation import QuotaReservation
    row = db.query(QuotaReservation).one()
    assert row.status == ('committed' if status == 200 else 'released')
    assert db.query(User).filter_by(user_id=account).one().quota_used == (42 if status == 200 else 0)
    assert db.query(UsageLog).one().cost_usd == (Decimal('0.082') if status == 200 else 0)


def test_price_snapshot_and_default_output_bound(db, account):
    from app.services.quota_reservation_service import QuotaReservationService
    from app.models.quota_reservation import QuotaReservation
    db.query(User).filter_by(user_id=account).update({'quota': 2000})
    db.commit()
    user, key = db.query(User).filter_by(user_id=account).one(), db.query(ApiKey).filter_by(key_id=account).one()
    service = ProxyService(db)
    request = {'messages': [{'role': 'user', 'content': '你好'}]}
    rid = service.reserve_quota(user, key, 'priced', request)
    assert request['max_tokens'] == 1024
    assert db.get(QuotaReservation, rid).estimated_tokens == 1082
    db.query(Model).filter_by(model_id='priced').update({'price_per_1k_input': 100, 'price_per_1k_output': 200})
    db.commit()
    tokens = {'prompt_tokens': 2, 'completion_tokens': 40, 'total_tokens': 42}
    service.record_usage(account, account, 'channel', 'priced', tokens, 1, 200)
    import asyncio
    loop = asyncio.new_event_loop()
    try:
        loop.run_until_complete(service.deduct_quota(user, key, tokens))
    finally:
        loop.close()
    from app.models.usage_log import UsageLog
    assert db.query(UsageLog).one().cost_usd == Decimal('0.082')
    assert db.get(QuotaReservation, rid).actual_cost_usd == Decimal('0.082')


def test_lease_renew_prevents_timeout_release(db, account):
    from app.services.quota_reservation_service import QuotaReservationService
    from app.models.quota_reservation import QuotaReservation
    rid = reserve(db, account)
    row = db.get(QuotaReservation, rid)
    row.expires_at = datetime.utcnow() - timedelta(seconds=1)
    db.commit()
    service = QuotaReservationService(db)
    with service.lease(rid):
        service.expire()
    assert db.get(QuotaReservation, rid).status == 'reserved'
    service.release(rid)


def test_redis_failure_denies_upstream_without_holding_quota(db, account, monkeypatch):
    from redis.exceptions import ConnectionError
    from app.models.quota_reservation import QuotaReservation
    class Unavailable:
        def eval(self, *args):
            raise ConnectionError('unavailable')
    monkeypatch.setattr('app.services.quota_reservation_service.get_rate_limit_redis_client', lambda: Unavailable())
    with pytest.raises(HTTPException) as exc:
        reserve(db, account)
    assert exc.value.status_code == 503
    assert db.query(QuotaReservation).count() == 0
    assert db.query(User).filter_by(user_id=account).one().quota_used == 0


def test_expired_record_cannot_be_charged_or_renewed(db, account):
    from app.models.quota_reservation import QuotaReservation
    from app.services.quota_reservation_service import QuotaReservationService
    rid = reserve(db, account)
    db.get(QuotaReservation, rid).expires_at = datetime.utcnow() - timedelta(seconds=1)
    db.commit()
    service = QuotaReservationService(db)
    service.expire()
    assert not service.commit(rid, {'total_tokens': 42})
    with pytest.raises(RuntimeError):
        service.renew(rid)
    assert db.query(User).filter_by(user_id=account).one().quota_used == 0


def test_upstream_overrun_cannot_spend_another_requests_reservation(db, account):
    from app.services.quota_reservation_service import QuotaReservationService
    service = QuotaReservationService(db)
    rid = reserve(db, account)
    with pytest.raises(HTTPException) as exc:
        service.commit(rid, {'prompt_tokens': 2, 'completion_tokens': 1000, 'total_tokens': 1002})
    assert exc.value.status_code == 502
    assert db.query(User).filter_by(user_id=account).one().quota_used == 0
    service.release(rid)


def test_migration_upgrade_downgrade_and_precreated_table():
    import importlib.util
    from pathlib import Path
    from sqlalchemy import create_engine, inspect
    from alembic.migration import MigrationContext
    from alembic.operations import Operations
    path = Path(__file__).parents[1] / 'alembic/versions/20260917_1100_quota_reservations.py'
    spec = importlib.util.spec_from_file_location('reservation_migration', path)
    migration = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(migration)
    engine = create_engine('sqlite://')
    with engine.begin() as conn:
        migration.op = Operations(MigrationContext.configure(conn))
        migration.upgrade()
        assert 'quota_reservations' in inspect(conn).get_table_names()
        migration.upgrade()
        migration.downgrade()
        assert 'quota_reservations' not in inspect(conn).get_table_names()
        migration.upgrade()
    engine.dispose()


def test_migration_on_mysql(db):
    import importlib.util
    from pathlib import Path
    from sqlalchemy import inspect
    from alembic.migration import MigrationContext
    from alembic.operations import Operations
    path = Path(__file__).parents[1] / 'alembic/versions/20260917_1100_quota_reservations.py'
    spec = importlib.util.spec_from_file_location('reservation_mysql_migration', path)
    migration = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(migration)
    # db fixture 已清空专用测试库；仅操作本任务的空表，最后恢复。
    with db.get_bind().begin() as conn:
        migration.op = Operations(MigrationContext.configure(conn))
        migration.upgrade()  # create_all 预建兼容
        migration.downgrade()
        migration.upgrade()
        inspector = inspect(conn)
        assert {i['name'] for i in inspector.get_indexes('quota_reservations')} == {
            'ix_quota_reservations_user_id', 'ix_quota_reservations_key_id', 'ix_reservation_expiry'}
        assert len(inspector.get_columns('quota_reservations')) == 18


@pytest.mark.parametrize('admin', [False, True])
def test_unlimited_and_admin_still_record_actual_usage(db, account, admin):
    from app.models.user import UserRole
    from app.services.quota_reservation_service import QuotaReservationService
    user = db.query(User).filter_by(user_id=account).one()
    user.quota = 0 if admin else -1
    user.role = UserRole.admin if admin else UserRole.user
    db.commit()
    rid = reserve(db, account)
    QuotaReservationService(db).commit(rid, {'prompt_tokens': 2, 'completion_tokens': 40, 'total_tokens': 42})
    db.refresh(user)
    assert user.quota_used == 42
    assert user.quota == (0 if admin else -1)


def test_stream_send_exception_closes_generator_and_releases(db, account):
    import asyncio
    from app.api.streaming import QuotaStreamingResponse
    from app.models.quota_reservation import QuotaReservation
    from app.services.quota_reservation_service import QuotaReservationService
    rid = reserve(db, account)
    closed = []
    def chunks():
        try:
            with QuotaReservationService(db).lease(rid):
                yield 'data: partial\n\n'
                yield 'data: more\n\n'
        finally:
            closed.append(True)
    response = QuotaStreamingResponse(chunks(), db.get_bind(), rid)
    async def receive():
        await asyncio.Event().wait()
    async def send(message):
        if message['type'] == 'http.response.body':
            raise OSError('client disconnected')
    loop = asyncio.new_event_loop()
    try:
        with pytest.raises(BaseException):
            loop.run_until_complete(response({'type': 'http', 'asgi': {'version': '3.0'}}, receive, send))
    finally:
        loop.close()
    db.rollback()
    assert closed == [True]
    assert db.get(QuotaReservation, rid).status == 'released'


def test_truncated_stream_is_not_successful(db, account, monkeypatch):
    import httpx
    from app.models.channel import Channel, ChannelType
    channel = Channel(channel_id='selected', name='test', type=ChannelType.openai,
                      endpoint='https://test.invalid', timeout=10, upstream_format='chat', auth_type='bearer')
    monkeypatch.setattr(ProxyService, 'select_channel', lambda *args: (channel, 'upstream', 'fake'))
    client = httpx.Client
    transport = httpx.MockTransport(lambda request: httpx.Response(200, text='data: {"choices":[{"delta":{"content":"partial"}}]}\n\n'))
    monkeypatch.setattr('app.services.proxy_service.httpx.Client', lambda **kw: client(transport=transport, **kw))
    service = ProxyService(db)
    user = db.query(User).filter_by(user_id=account).one()
    key = db.query(ApiKey).filter_by(key_id=account).one()
    request = {'messages': [{'role': 'user', 'content': 'hi'}], 'max_tokens': 100}
    service.reserve_quota(user, key, 'priced', request)
    list(service.forward_stream('priced', user, key, request))
    assert service.stream_metadata['status_code'] == 502
    assert not service.stream_metadata.get('completed')
    service.release_reservation()
    from app.models.quota_reservation import QuotaReservation
    assert db.get(QuotaReservation, service.reservation_id).status == 'released'


def test_reserved_request_requires_real_consistent_usage(db, account):
    service = ProxyService(db)
    reserve(db, account)
    from app.models.quota_reservation import QuotaReservation
    service.reservation_id = db.query(QuotaReservation).one().reservation_id
    for response in [
        {'choices': [{'message': {'content': '您好'}}]},
        {'usage': {'prompt_tokens': -2, 'completion_tokens': 42, 'total_tokens': 40}},
        {'usage': {'prompt_tokens': 2, 'completion_tokens': 40, 'total_tokens': 1}},
    ]:
        with pytest.raises(HTTPException) as exc:
            service.calculate_tokens({'messages': [{'content': '你好'}]}, response)
        assert exc.value.status_code == 502
    service.release_reservation()


def test_proxy_stream_allows_renewal_with_single_connection_pool(db, account, monkeypatch):
    import asyncio
    import httpx
    from sqlalchemy import create_engine
    from sqlalchemy.orm import sessionmaker
    from starlette.requests import Request
    from app.api.v1 import proxy
    from app.models.channel import Channel, ChannelType
    from app.models.quota_reservation import QuotaReservation
    from app.services.quota_reservation_service import QuotaReservationService
    import app.core.database as database
    db.add(Channel(channel_id='pooled', name='test', type=ChannelType.openai,
                   endpoint='https://test.invalid', timeout=10, upstream_format='chat', auth_type='bearer', api_key='fake'))
    db.commit()
    engine = create_engine(db.get_bind().url, pool_size=1, max_overflow=0, pool_timeout=0.2)
    sessions = sessionmaker(bind=engine)
    monkeypatch.setattr(database, 'SessionLocal', sessions)
    monkeypatch.setattr(ProxyService, 'check_model_group_access', lambda *args: {'allowed': True})
    monkeypatch.setattr(ProxyService, 'select_channel', lambda self, *args: (self.db.query(Channel).filter_by(channel_id='pooled').one(), 'upstream', 'fake'))
    renewed = []
    class LongStream(httpx.SyncByteStream):
        def __iter__(self):
            yield b'data: {"choices":[{"delta":{"content":"hello"}}]}\n\n'
            # 上游仍在读取时尝试续期；池只有一个连接，不能被请求 session 占住。
            with sessions() as check:
                rid = check.query(QuotaReservation).filter_by(user_id=account).one().reservation_id
                QuotaReservationService(check).renew(rid)
                renewed.append(True)
            yield b'data: {"usage":{"prompt_tokens":2,"completion_tokens":40,"total_tokens":42}}\n\ndata: [DONE]\n\n'
    real_client = httpx.Client
    monkeypatch.setattr('app.services.proxy_service.httpx.Client', lambda **kw: real_client(
        transport=httpx.MockTransport(lambda req: httpx.Response(200, stream=LongStream())), **kw))
    with sessions() as session:
        request = Request({'type': 'http', 'headers': []})
        request.state.user = session.query(User).filter_by(user_id=account).one()
        request.state.api_key = session.query(ApiKey).filter_by(key_id=account).one()
        loop = asyncio.new_event_loop()
        async def consume():
            response = await proxy.chat_completions(request, proxy.ChatCompletionRequest(
                model='priced', messages=[{'role': 'user', 'content': 'hi'}], max_tokens=100, stream=True), session)
            async def receive():
                await asyncio.Event().wait()
            async def send(message):
                if b'[DONE]' in message.get('body', b''):
                    with sessions() as check:
                        assert check.query(QuotaReservation).filter_by(user_id=account).one().status == 'committed'
            await response({'type': 'http', 'asgi': {'version': '3.0'}}, receive, send)
        try:
            loop.run_until_complete(consume())
        finally:
            loop.close()
    with sessions() as check:
        assert check.query(QuotaReservation).filter_by(user_id=account).one().status == 'committed'
    assert renewed == [True]
    engine.dispose()
