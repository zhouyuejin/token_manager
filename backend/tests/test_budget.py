"""真实数据库预算准入、消费与持久化告警。"""
import asyncio
import uuid
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime
from decimal import Decimal

import pytest
from fastapi import HTTPException

from app.models.user import User, UserRole
from app.models.api_key import ApiKey
from app.models.model import Model
from app.models.organization import Department
from app.models.project import Project
from app.models.quota_reservation import QuotaReservation
from app.models.notification import Notification
from app.models.usage_log import UsageLog
from app.services.quota_reservation_service import QuotaReservationService


def run_async(coroutine):
    loop = asyncio.new_event_loop()
    try:
        return loop.run_until_complete(coroutine)
    finally:
        loop.close()


@pytest.fixture(scope='module', autouse=True)
def budget_schema(engine):
    import importlib.util
    from pathlib import Path
    from alembic.migration import MigrationContext
    from alembic.operations import Operations
    spec = importlib.util.spec_from_file_location('budget_migration', Path(__file__).parents[1] / 'alembic/versions/20260918_1200_budgets.py')
    migration = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(migration)
    with engine.begin() as conn:
        migration.op = Operations(MigrationContext.configure(conn))
        migration.upgrade()  # 仅更新专用测试库 schema。
    return migration


@pytest.fixture
def scope(db):
    db.add_all([Department(dept_id='d', name='部门', owner_user_id='owner'),
                User(user_id='owner', username='owner', email='owner@test', password='hash', quota=-1),
                User(user_id='admin', username='admin', email='admin@test', password='hash', role=UserRole.admin),
                Model(model_id='priced', price_per_1k_input=0, price_per_1k_output=1)])
    db.flush()
    db.add(Project(project_id='p', dept_id='d', name='项目', owner_user_id='owner'))
    db.commit()
    return {'project_id': 'p', 'department_id': 'd'}


def add_budget(db, scope_type='project', amount='0.15', month=None, policy='block'):
    from app.models.budget import Budget
    from app.services.budget_service import current_month
    row = Budget(budget_id=uuid.uuid4().hex, scope_type=scope_type,
                 scope_id='p' if scope_type == 'project' else 'd',
                 month=month or current_month(), amount_usd=Decimal(amount),
                 thresholds=[80, 90, 100], policy=policy, enabled=True)
    db.add(row)
    db.commit()
    return row


def reserve(db, attribution, uid='owner', output=100):
    user = db.query(User).filter_by(user_id=uid).one()
    key = db.query(ApiKey).filter_by(key_id=uid).first()
    if key is None:
        key = ApiKey(key_id=uid, user_id=uid, api_key=uid, key_name='test', project_id='p')
        db.add(key)
        db.commit()
    return QuotaReservationService(db).reserve(user, key, 'priced',
        {'messages': [], 'max_tokens': output}, attribution)


def test_pending_reservations_block_and_release_restores_budget(db, scope):
    add_budget(db)
    rid = reserve(db, scope)
    with pytest.raises(HTTPException) as error:
        reserve(db, scope)
    assert error.value.status_code == 403
    assert '预算' in error.value.detail and '项目' in error.value.detail
    QuotaReservationService(db).release(rid)
    assert reserve(db, scope)


def test_department_budget_blocks_otherwise_unlimited_project(db, scope):
    add_budget(db, 'department', '0.05')
    with pytest.raises(HTTPException) as error:
        reserve(db, scope)
    assert '部门' in error.value.detail
    assert db.query(QuotaReservation).count() == 0


def test_twenty_users_cannot_overdraw_shared_budget(db, scope, SessionLocal):
    add_budget(db)
    for i in range(20):
        uid = f'u{i}'
        db.add(User(user_id=uid, username=uid, email=uid+'@test', password='hash', quota=-1))
        db.add(ApiKey(key_id=uid, user_id=uid, api_key=uid, key_name='test', project_id='p'))
    db.commit()
    def attempt(i):
        with SessionLocal() as session:
            try:
                return reserve(session, scope, f'u{i}')
            except HTTPException as exc:
                assert exc.status_code == 403
                return None
    with ThreadPoolExecutor(max_workers=20) as pool:
        assert sum(bool(rid) for rid in pool.map(attempt, range(20))) == 1


def test_actual_consumption_and_legacy_logs_are_counted_once(db, scope):
    from app.services.budget_service import BudgetService
    budget = add_budget(db, amount='1')
    db.add(UsageLog(log_id='legacy', user_id='owner', key_id='owner', model='priced',
                   project_id='p', department_id='d', cost_usd=Decimal('0.2'), status_code=200))
    db.commit()
    rid = reserve(db, scope)
    QuotaReservationService(db).commit(rid, {'prompt_tokens': 0, 'completion_tokens': 80, 'total_tokens': 80})
    db.add(UsageLog(log_id='linked', user_id='owner', key_id='owner', model='priced',
                   project_id='p', department_id='d', reservation_id=rid,
                   cost_usd=Decimal('0.08'), status_code=200))
    db.commit()
    summary = BudgetService(db).summary(budget)
    assert summary['used_usd'] == Decimal('0.28')
    assert summary['reserved_usd'] == 0
    assert summary['remaining_usd'] == Decimal('0.72')


def test_threshold_once_per_month_and_websocket_failure_isolated(db, scope, monkeypatch):
    from app.services.budget_service import BudgetService
    add_budget(db, amount='0.1', policy='alert')
    async def broken(*args):
        raise OSError('disconnected')
    monkeypatch.setattr('app.services.ws_manager.manager.send_to_user', broken)
    rid = reserve(db, scope)
    QuotaReservationService(db).commit(rid, {'prompt_tokens': 0, 'completion_tokens': 79, 'total_tokens': 79})
    run_async(BudgetService(db).check_alerts())
    assert db.query(Notification).count() == 0
    rid = reserve(db, scope)
    QuotaReservationService(db).commit(rid, {'prompt_tokens': 0, 'completion_tokens': 21, 'total_tokens': 21})
    run_async(BudgetService(db).check_alerts())
    run_async(BudgetService(db).check_alerts())
    notifications = db.query(Notification).all()
    assert len(notifications) == 6  # 三个阈值，各通知负责人和管理员，去重。
    assert {n.user_id for n in notifications} == {'owner', 'admin'}
    assert reserve(db, scope)  # 仅告警策略超过预算仍可准入。


def test_previous_month_does_not_block_current_month(db, scope):
    add_budget(db, amount='0.01', month='2020-01')
    assert reserve(db, scope)


def test_beijing_month_boundary():
    from app.services.budget_service import current_month, month_bounds
    assert current_month(datetime(2026, 9, 30, 15, 59)) == '2026-09'
    assert current_month(datetime(2026, 9, 30, 16)) == '2026-10'
    assert month_bounds('2026-10') == (datetime(2026, 9, 30, 16), datetime(2026, 10, 31, 16))


def test_upgrade_legacy_ledger_and_log_are_not_double_counted(db, scope):
    from app.services.budget_service import BudgetService
    budget = add_budget(db, amount='1')
    rid = reserve(db, scope)
    QuotaReservationService(db).commit(rid, {'prompt_tokens': 0, 'completion_tokens': 80, 'total_tokens': 80})
    # 升级前的账本及日志没有稳定关联，旧消费采用日志，新消费采用账本。
    row = db.get(QuotaReservation, rid)
    row.budget_accounted = False
    db.add(UsageLog(log_id='before-upgrade', user_id='owner', key_id='owner', model='priced',
                   project_id='p', department_id='d', cost_usd=Decimal('0.08'), status_code=200))
    db.commit()
    assert BudgetService(db).summary(budget)['used_usd'] == Decimal('0.08')


def test_sub_precision_estimate_does_not_disappear_from_pending_budget(db, scope):
    add_budget(db, amount='0.00000001')
    db.query(Model).filter_by(model_id='priced').update({'price_per_1k_output': Decimal('0.000001')})
    db.commit()
    rid = reserve(db, scope, output=1)
    assert db.get(QuotaReservation, rid).estimated_cost_usd == Decimal('0.00000001')
    with pytest.raises(HTTPException):
        reserve(db, scope, output=1)


@pytest.fixture
def billing_client(db, scope):
    from fastapi import FastAPI
    from fastapi.testclient import TestClient
    from app.api.v1.billing import router
    from app.core.database import get_db
    from app.dependencies import get_current_user
    app = FastAPI()
    app.include_router(router, prefix='/billing')
    app.dependency_overrides[get_db] = lambda: db
    app.dependency_overrides[get_current_user] = lambda: db.query(User).filter_by(user_id='admin').one()
    return TestClient(app)


def test_admin_can_configure_update_disable_and_view_budget(billing_client, db, scope):
    payload = {'amount_usd': '0.05', 'thresholds': [100, 80], 'policy': 'block'}
    response = billing_client.put('/billing/budgets/project/p/2026-09', json=payload)
    assert response.status_code == 200, response.text
    bid = response.json()['budget_id']
    assert response.json()['thresholds'] == [80, 100]
    response = billing_client.put('/billing/budgets/project/p/2026-09', json={**payload, 'enabled': False})
    assert response.json()['budget_id'] == bid
    assert billing_client.get('/billing/budgets', params={'month': '2026-09'}).json()['items'][0]['enabled'] is False
    assert reserve(db, scope)


@pytest.mark.parametrize('payload', [
    {'amount_usd': '-1'}, {'amount_usd': 'NaN'}, {'amount_usd': 'Infinity'},
    {'amount_usd': '0.000000001'}, {'amount_usd': '10000000000'},
    {'amount_usd': '1', 'thresholds': []}, {'amount_usd': '1', 'thresholds': [80, 80]},
    {'amount_usd': '1', 'thresholds': [0]}, {'amount_usd': '1', 'thresholds': [101]},
    {'amount_usd': '1', 'thresholds': [True]}, {'amount_usd': '1', 'thresholds': [80.5]},
    {'amount_usd': '1', 'policy': 'unknown'}
])
def test_invalid_budget_configuration_rejected(billing_client, payload):
    assert billing_client.put('/billing/budgets/project/p/2026-09', json=payload).status_code == 422


def test_month_scope_and_admin_access_validation(billing_client, db):
    from app.dependencies import get_current_user
    assert billing_client.put('/billing/budgets/project/missing/2026-09', json={'amount_usd': '1'}).status_code == 404
    assert billing_client.put('/billing/budgets/user/owner/2026-09', json={'amount_usd': '1'}).status_code == 422
    for month in ['2026-13', '2026-9', 'bad', '9999-12']:
        assert billing_client.get('/billing/budgets', params={'month': month}).status_code == 422
    billing_client.app.dependency_overrides[get_current_user] = lambda: db.query(User).filter_by(user_id='owner').one()
    assert billing_client.get('/billing/budgets').status_code == 403
    assert billing_client.put('/billing/budgets/project/p/2026-09', json={'amount_usd': '1'}).status_code == 403


def test_cost_overrun_rejected_even_when_total_tokens_fit_reservation(db, scope):
    db.query(Model).filter_by(model_id='priced').update({'price_per_1k_input': 10})
    db.commit()
    rid = reserve(db, scope)
    with pytest.raises(HTTPException) as error:
        QuotaReservationService(db).commit(rid, {'prompt_tokens': 100, 'completion_tokens': 0, 'total_tokens': 100})
    assert error.value.status_code == 502
    assert db.get(QuotaReservation, rid).status == 'reserved'


def test_late_settlement_stays_in_reservation_month_and_alerts(db, scope):
    from app.services.budget_service import BudgetService
    budget = add_budget(db, amount='0.08', month='2020-01', policy='alert')
    rid = reserve(db, scope)
    db.get(QuotaReservation, rid).created_at = datetime(2020, 1, 15)
    db.commit()
    QuotaReservationService(db).commit(rid, {'prompt_tokens': 0, 'completion_tokens': 80, 'total_tokens': 80})
    assert BudgetService(db).summary(budget)['used_usd'] == Decimal('0.08')
    run_async(BudgetService(db).check_alerts())
    assert db.query(Notification).count() == 6


def test_expired_reservation_returns_budget(db, scope):
    from datetime import timedelta
    add_budget(db)
    rid = reserve(db, scope)
    db.get(QuotaReservation, rid).expires_at = datetime.utcnow() - timedelta(seconds=1)
    db.commit()
    QuotaReservationService(db).expire()
    assert reserve(db, scope)


def test_parallel_alert_checks_do_not_duplicate_notifications(db, scope, SessionLocal):
    from app.services.budget_service import BudgetService
    add_budget(db, amount='0.1', policy='alert')
    rid = reserve(db, scope)
    QuotaReservationService(db).commit(rid, {'prompt_tokens': 0, 'completion_tokens': 100, 'total_tokens': 100})
    def scan(_):
        with SessionLocal() as session:
            run_async(BudgetService(session).check_alerts())
    with ThreadPoolExecutor(max_workers=4) as pool:
        list(pool.map(scan, range(4)))
    db.rollback()
    assert db.query(Notification).count() == 6


def test_migration_roundtrip_preserves_old_usage():
    import importlib.util
    from pathlib import Path
    from sqlalchemy import create_engine, text, inspect
    from alembic.migration import MigrationContext
    from alembic.operations import Operations
    engine = create_engine('sqlite://')
    with engine.begin() as conn:
        conn.execute(text('CREATE TABLE usage_logs (log_id VARCHAR(50) PRIMARY KEY, cost_usd NUMERIC(18,8), project_id VARCHAR(32), department_id VARCHAR(32), created_at DATETIME)'))
        conn.execute(text("INSERT INTO usage_logs (log_id, cost_usd) VALUES ('old', 0.2)"))
        conn.execute(text('CREATE TABLE quota_reservations (reservation_id VARCHAR(32) PRIMARY KEY, project_id VARCHAR(32), department_id VARCHAR(32), created_at DATETIME)'))
        conn.execute(text("INSERT INTO quota_reservations (reservation_id) VALUES ('old')"))
        path = Path(__file__).parents[1] / 'alembic/versions/20260918_1200_budgets.py'
        spec = importlib.util.spec_from_file_location('budget_roundtrip', path)
        migration = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(migration)
        migration.op = Operations(MigrationContext.configure(conn))
        migration.upgrade()
        migration.upgrade()
        assert conn.execute(text('SELECT budget_accounted FROM quota_reservations')).scalar() == 0
        migration.downgrade()
        assert conn.execute(text('SELECT cost_usd FROM usage_logs')).scalar() == 0.2
        assert 'budgets' not in inspect(conn).get_table_names()
        migration.upgrade()
    engine.dispose()


@pytest.mark.parametrize('chat', [False, True])
@pytest.mark.parametrize('stream', [False, True])
def test_budget_block_reaches_all_four_entrypoints(db, scope, monkeypatch, chat, stream):
    from fastapi import FastAPI
    from fastapi.testclient import TestClient
    from app.core.database import get_db
    from app.dependencies import get_current_user
    from app.api.v1 import proxy, chat as chat_module
    from app.models.chat import ChatConversation
    from app.services.proxy_service import ProxyService
    add_budget(db, amount='0.05')
    key = ApiKey(key_id='owner', user_id='owner', api_key='owner', key_name='test', project_id='p')
    db.add(key)
    db.add(ChatConversation(conversation_id='conv', user_id='owner', model_id='priced'))
    db.commit()
    user = db.query(User).filter_by(user_id='owner').one()
    monkeypatch.setattr(ProxyService, 'check_model_group_access', lambda *args: {'allowed': True})
    monkeypatch.setattr(chat_module, 'get_user_api_key', lambda *args: key)
    app = FastAPI()
    app.include_router(chat_module.router if chat else proxy.router, prefix='/api')
    app.dependency_overrides[get_db] = lambda: db
    app.dependency_overrides[get_current_user] = lambda: user
    @app.middleware('http')
    async def auth(request, call_next):
        request.state.user, request.state.api_key = user, key
        return await call_next(request)
    response = TestClient(app).post('/api/conv/messages' if chat else '/api/chat/completions', json={
        'model': 'priced', 'messages': [{'role': 'user', 'content': 'hi'}], 'max_tokens': 100, 'stream': stream
    })
    assert response.status_code == 403, response.text
    assert '预算' in response.json()['detail']
    assert db.query(QuotaReservation).count() == 0


def test_mysql_migration_roundtrip_keeps_historical_cost_once(db, scope, budget_schema):
    from alembic.migration import MigrationContext
    from alembic.operations import Operations
    from app.services.budget_service import BudgetService
    rid = reserve(db, scope)
    QuotaReservationService(db).commit(rid, {'prompt_tokens': 0, 'completion_tokens': 80, 'total_tokens': 80})
    db.add(UsageLog(log_id='old-linked', user_id='owner', key_id='owner', model='priced',
                   project_id='p', department_id='d', reservation_id=rid,
                   cost_usd=Decimal('0.08'), status_code=200))
    db.commit()
    with db.get_bind().begin() as conn:
        budget_schema.op = Operations(MigrationContext.configure(conn))
        budget_schema.downgrade()
        budget_schema.upgrade()
        budget_schema.upgrade()
    db.expire_all()
    assert db.query(UsageLog).one().cost_usd == Decimal('0.08')
    assert db.get(QuotaReservation, rid).budget_accounted is False
    budget = add_budget(db, amount='1')
    assert BudgetService(db).summary(budget)['used_usd'] == Decimal('0.08')


def test_sub_precision_actual_charge_cannot_reuse_budget_forever(db, scope):
    add_budget(db, amount='0.00000001')
    db.query(Model).filter_by(model_id='priced').update({'price_per_1k_output': Decimal('0.000001')})
    db.commit()
    rid = reserve(db, scope, output=1)
    QuotaReservationService(db).commit(rid, {'prompt_tokens': 0, 'completion_tokens': 1, 'total_tokens': 1})
    assert db.get(QuotaReservation, rid).actual_cost_usd == Decimal('0.00000001')
    with pytest.raises(HTTPException):
        reserve(db, scope, output=1)


def test_two_users_reserving_each_others_scope_do_not_deadlock(db, scope, SessionLocal, monkeypatch):
    from threading import Barrier
    from app.services.budget_service import BudgetService
    db.add_all([Department(dept_id='d2', name='部门2'),
                User(user_id='other', username='other', email='other@test', password='hash', quota=-1)])
    db.flush()
    db.add(Project(project_id='p2', dept_id='d2', name='项目2'))
    db.add(ApiKey(key_id='other', user_id='other', api_key='other', key_name='test', project_id='p2'))
    db.commit()
    other_scope = {'project_id': 'p2', 'department_id': 'd2'}
    add_budget(db, amount='1')
    from app.models.budget import Budget
    from app.services.budget_service import current_month
    db.add(Budget(budget_id='other', scope_type='project', scope_id='p2', month=current_month(),
                  amount_usd=1, thresholds=[80, 90, 100], policy='block', enabled=True))
    db.commit()
    reserve(db, scope)
    reserve(db, other_scope, 'other')
    barrier = Barrier(2)
    admit = BudgetService.admit
    def synchronized_admit(service, budgets, amount):
        barrier.wait(timeout=5)
        return admit(service, budgets, amount)
    monkeypatch.setattr(BudgetService, 'admit', synchronized_admit)
    def attempt(pair):
        uid, attribution = pair
        with SessionLocal() as session:
            return reserve(session, attribution, uid)
    with ThreadPoolExecutor(max_workers=2) as pool:
        assert all(pool.map(attempt, [('owner', other_scope), ('other', scope)]))


def test_failover_attempt_logs_share_reservation_without_double_billing(db, scope):
    from app.services.proxy_service import ProxyService
    from app.services.budget_service import BudgetService
    budget = add_budget(db, amount='1')
    rid = reserve(db, scope)
    service = ProxyService(db)
    service.reservation_id = rid
    service._record_usage_failure('owner', 'owner', 'channel1', 'priced', 503, 'retry')
    service._record_usage_failure('owner', 'owner', 'channel2', 'priced', 503, 'retry')
    tokens = {'prompt_tokens': 0, 'completion_tokens': 80, 'total_tokens': 80}
    service.record_usage('owner', 'owner', 'channel3', 'priced', tokens, 1, 200)
    run_async(service.deduct_quota(db.query(User).filter_by(user_id='owner').one(),
                                  db.query(ApiKey).filter_by(key_id='owner').one(), tokens))
    assert db.query(UsageLog).count() == 3
    assert BudgetService(db).summary(budget)['used_usd'] == Decimal('0.08')
