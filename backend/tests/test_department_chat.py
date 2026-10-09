"""网页调用使用真实 MySQL/Redis 账本，仅替换外部模型 HTTP。"""
import asyncio
import json
import uuid
from decimal import Decimal
from types import SimpleNamespace

import httpx
import pytest
from fastapi import FastAPI, HTTPException
from fastapi.testclient import TestClient
from starlette.requests import Request

from app.api.v1 import admin, chat, projects
from app.core.database import get_db
from app.dependencies import get_current_user
from app.models.api_key import ApiKey
from app.models.budget import Budget
from app.models.channel import Channel, ChannelType
from app.models.chat import ChatConversation
from app.models.model import Model
from app.models.organization import Department
from app.models.quota_reservation import QuotaReservation
from app.models.usage_log import UsageLog
from app.models.user import User, UserRole
from app.schemas.admin import AdminUserCreate, AdminUserUpdate
from app.services.budget_service import current_month
from app.services.proxy_service import ProxyService


@pytest.fixture
def member(db):
    uid = uuid.uuid4().hex
    department = Department(dept_id='dept_chat', name='日常使用', content_audit_enabled=True)
    db.add(department)
    db.flush()
    user = User(user_id=uid, username=uid, email=uid+'@test', password='hash',
                department_id=department.dept_id, quota=10000)
    db.add_all([user, Model(model_id='priced', price_per_1k_input=1, price_per_1k_output=2)])
    db.commit()
    return user


def request(method='PUT'):
    return Request({'type': 'http', 'method': method, 'headers': [], 'client': ('127.0.0.1', 1)})


def test_admin_assigns_and_clears_department(db, member):
    operator = SimpleNamespace(user_id='operator', username='operator', role=UserRole.admin)
    asyncio.run(admin.update_user(member.user_id, AdminUserUpdate(department_id=None), request(), db, operator))
    assert db.get(User, member.id).department_id is None
    asyncio.run(admin.update_user(member.user_id, AdminUserUpdate(department_id='dept_chat'), request(), db, operator))
    result = asyncio.run(admin.get_user(member.user_id, db, operator))
    assert result.department_id == 'dept_chat'
    assert result.department_name == '日常使用'
    with pytest.raises(HTTPException) as error:
        asyncio.run(admin.update_user(member.user_id, AdminUserUpdate(department_id='missing'), request(), db, operator))
    assert error.value.status_code in (404, 422)
    assert db.get(User, member.id).department_id == 'dept_chat'


def test_admin_can_assign_own_department(db, member):
    member.role = UserRole.admin
    db.commit()
    asyncio.run(admin.update_user(member.user_id, AdminUserUpdate(department_id=None), request(), db, member))
    assert member.department_id is None


def test_department_with_members_cannot_be_deleted(db, member):
    with pytest.raises(HTTPException) as error:
        asyncio.run(projects.delete_department('dept_chat', request('DELETE'), member, db))
    assert error.value.status_code == 409
    assert db.get(Department, 'dept_chat') is not None


@pytest.fixture
def chat_client(db, member, monkeypatch):
    channel = Channel(channel_id='selected', name='test', type=ChannelType.openai,
                      endpoint='https://test.invalid', timeout=10, upstream_format='chat', auth_type='bearer')
    monkeypatch.setattr(ProxyService, 'check_model_group_access', lambda *args: {'allowed': True})
    monkeypatch.setattr(ProxyService, 'select_channel', lambda *args: (channel, 'upstream', 'fake'))
    monkeypatch.setattr(ProxyService, 'select_candidates', lambda *args: [(channel, SimpleNamespace(upstream_model='upstream'), 'fake')])
    calls = []
    upstream_state = {'status': 200, 'ending': True, 'change_department': False}
    def upstream(req):
        payload = json.loads(req.content)
        calls.append(payload)
        if upstream_state['change_department']:
            member.department_id = 'dept_second'
            db.get(Department, 'dept_chat').content_audit_enabled = False
            db.commit()
        if upstream_state['status'] != 200:
            return httpx.Response(upstream_state['status'], json={'error': {'message': 'upstream failed'}})
        if payload.get('stream'):
            return httpx.Response(200, text='data: '+json.dumps({'choices': [{'delta': {'content': 'hello'}}]})+'\n\n'
                +'data: '+json.dumps({'choices': [], 'usage': {'prompt_tokens': 2, 'completion_tokens': 40, 'total_tokens': 42}})+'\n\n'
                +('data: [DONE]\n\n' if upstream_state['ending'] else ''))
        return httpx.Response(200, json={'choices': [{'message': {'content': 'hello'}}],
            'usage': {'prompt_tokens': 2, 'completion_tokens': 40, 'total_tokens': 42}})
    real_client = httpx.Client
    monkeypatch.setattr('app.services.proxy_service.httpx.Client', lambda **kw: real_client(transport=httpx.MockTransport(upstream), **kw))
    db.add(ChatConversation(conversation_id='conv', user_id=member.user_id, model_id='priced'))
    db.commit()
    app = FastAPI()
    app.include_router(chat.router, prefix='/chats')
    app.dependency_overrides[get_db] = lambda: db
    app.dependency_overrides[get_current_user] = lambda: member
    @app.middleware('http')
    async def identify(req, call_next):
        req.state.request_id = 'department-chat-request'
        return await call_next(req)
    client = TestClient(app)
    client.upstream_state = upstream_state
    return client, calls


def send(client, stream=False):
    return client.post('/chats/conv/messages', json={'model': 'priced', 'messages': [
        {'role': 'user', 'content': 'phone 13800138000'}], 'max_tokens': 100, 'stream': stream})


@pytest.mark.parametrize('stream', [False, True])
def test_department_member_chats_without_key_or_project(db, member, chat_client, stream):
    client, calls = chat_client
    response = send(client, stream)
    assert response.status_code == 200, response.text
    assert 'hello' in response.text
    assert calls
    db.rollback()
    row = db.query(QuotaReservation).one()
    log = db.query(UsageLog).one()
    assert (row.key_id, row.project_id, row.department_id) == (None, None, 'dept_chat')
    assert (log.key_id, log.project_id, log.department_id) == (None, None, 'dept_chat')
    assert row.status == 'committed'
    assert row.actual_cost_cny == log.cost_cny == Decimal('0.082')
    assert db.query(User).filter_by(user_id=member.user_id).one().quota_used == 42
    assert '13800138000' not in log.request_summary
    assert db.query(ApiKey).count() == 0


@pytest.mark.parametrize('department', [None, 'disabled'])
def test_invalid_department_denies_upstream(db, member, chat_client, department):
    client, calls = chat_client
    if department is None:
        member.department_id = None
    else:
        db.get(Department, 'dept_chat').status = 'disabled'
    db.commit()
    response = send(client)
    assert response.status_code == 403, response.text
    assert calls == []
    assert db.query(QuotaReservation).count() == 0


def test_department_budget_blocks_chat(db, member, chat_client):
    client, calls = chat_client
    db.add(Budget(budget_id='budget_chat', scope_type='department', scope_id='dept_chat',
        month=current_month(), amount_cny=Decimal('0.001'), policy='block', enabled=True, thresholds=[]))
    db.commit()
    response = send(client)
    assert response.status_code == 403, response.text
    assert calls == []
    assert db.query(QuotaReservation).count() == 0


def test_department_stats_include_web_usage(db, member):
    from datetime import date
    db.get(Department, 'dept_chat').owner_user_id = member.user_id
    db.add(UsageLog(log_id='web', user_id=member.user_id, key_id=None, project_id=None,
        department_id='dept_chat', model='priced', total_tokens=42, cost_cny=Decimal('0.082'), status_code=200))
    db.commit()
    result = asyncio.run(projects.get_department_usage_stats(date.today(), date.today(), 'dept_chat', member, db))
    assert result['total_requests'] == 1
    assert result['web_chat'] == {'tokens': 42, 'requests': 1, 'cost': 0.082}
    assert result['by_project'] == []


def test_my_billing_and_filters_include_department_without_keys(db, member):
    from app.api.v1.stats import get_my_billing, get_my_usage_options
    db.add(Budget(budget_id='budget_chat', scope_type='department', scope_id='dept_chat',
        month=current_month(), amount_cny=Decimal('10'), policy='block', enabled=True, thresholds=[]))
    db.commit()
    billing = asyncio.run(get_my_billing(member, db))
    assert [row['scope_id'] for row in billing['budgets']] == ['dept_chat']
    options = asyncio.run(get_my_usage_options(member, db))
    assert options['departments'] == [{'department_id': 'dept_chat', 'name': '日常使用'}]


@pytest.mark.parametrize('stream', [False, True])
def test_existing_project_key_never_controls_web_accounting(db, member, chat_client, stream):
    from app.models.project import Project, UserProject
    client, _ = chat_client
    db.add(Department(dept_id='dept_other', name='Other'))
    db.flush()
    db.add(Project(project_id='external_project', dept_id='dept_other', name='External', content_audit_enabled=False))
    db.flush()
    db.add_all([UserProject(user_id=member.user_id, project_id='external_project'),
        ApiKey(key_id='external_key', user_id=member.user_id, api_key='tmk_external', key_name='External', project_id='external_project'),
        Budget(budget_id='blocked_project', scope_type='project', scope_id='external_project',
            month=current_month(), amount_cny=0, policy='block', enabled=True, thresholds=[])])
    db.commit()
    response = send(client, stream)
    assert response.status_code == 200, response.text
    db.rollback()
    log = db.query(UsageLog).one()
    assert (log.department_id, log.project_id, log.key_id) == ('dept_chat', None, None)
    assert db.query(ApiKey).one().last_used_at is None


def test_department_and_audit_snapshot_survive_transfer_during_call(db, member, chat_client):
    client, _ = chat_client
    db.add(Department(dept_id='dept_second', name='New department'))
    db.commit()
    client.upstream_state['change_department'] = True
    response = send(client)
    assert response.status_code == 200, response.text
    db.rollback()
    log = db.query(UsageLog).one()
    assert log.department_id == 'dept_chat'
    assert log.request_summary is not None
    assert db.query(User).filter_by(user_id=member.user_id).one().department_id == 'dept_second'


@pytest.mark.parametrize('stream', [False, True])
def test_upstream_failure_releases_user_concurrency_and_reservation(db, member, chat_client, stream):
    from app.services.rate_limit_service import get_rate_limit_redis_client
    client, _ = chat_client
    member.concurrency_limit = 1
    db.commit()
    client.upstream_state['status'] = 503
    response = send(client, stream)
    assert response.status_code == (200 if stream else 503), response.text
    db.rollback()
    assert db.query(QuotaReservation).one().status == 'released'
    assert db.query(UsageLog).one().key_id is None
    assert db.query(User).filter_by(user_id=member.user_id).one().quota_used == 0
    assert int(get_rate_limit_redis_client().get('rl:concurrency:user:' + member.user_id) or 0) == 0


def test_web_user_quota_blocks_before_upstream(db, member, chat_client):
    client, calls = chat_client
    member.quota = 1
    db.commit()
    response = send(client)
    assert response.status_code == 403, response.text
    assert calls == []
    assert db.query(QuotaReservation).count() == 0


def test_department_audit_disabled_keeps_usage_without_summaries(db, member, chat_client):
    client, _ = chat_client
    db.get(Department, 'dept_chat').content_audit_enabled = False
    db.commit()
    response = send(client)
    assert response.status_code == 200, response.text
    log = db.query(UsageLog).one()
    assert log.department_id == 'dept_chat'
    assert log.request_summary is log.response_summary is None


def test_web_stream_disconnect_releases_real_concurrency_and_reservation(db, member, chat_client):
    from app.services.rate_limit_service import get_rate_limit_redis_client
    member.concurrency_limit = 1
    db.commit()
    req = request('POST')
    req.state.request_id = 'cancelled-chat'
    response = asyncio.run(chat.send_message('conv', chat.ChatSendMessageRequest(
        model='priced', messages=[{'role': 'user', 'content': 'hi'}], max_tokens=100, stream=True), req, member, db))
    async def receive():
        await asyncio.Event().wait()
    async def disconnect(message):
        if message['type'] == 'http.response.body':
            raise OSError('client disconnected')
    with pytest.raises(BaseException):
        asyncio.run(response({'type': 'http', 'asgi': {'version': '3.0'}}, receive, disconnect))
    db.rollback()
    assert db.query(QuotaReservation).one().status == 'released'
    assert db.query(User).filter_by(user_id=member.user_id).one().quota_used == 0
    assert int(get_rate_limit_redis_client().get('rl:concurrency:user:' + member.user_id) or 0) == 0


@pytest.mark.parametrize('role', ['user', 'department_admin', 'auditor', 'admin'])
def test_department_assignment_http_requires_admin_write(db, member, role):
    from app.core.security import create_access_token
    operator = User(user_id='operator', username='operator', email='operator@test', password='hash', role=UserRole(role))
    db.add(operator)
    db.commit()
    app = FastAPI()
    app.include_router(admin.router, prefix='/api/v1/admin')
    app.dependency_overrides[get_db] = lambda: db
    token = create_access_token({'sub': operator.user_id, 'username': operator.username})
    response = TestClient(app).put('/api/v1/admin/users/' + member.user_id,
        headers={'Authorization': 'Bearer ' + token}, json={'department_id': None})
    assert response.status_code == (200 if role == 'admin' else 403), response.text
    db.refresh(member)
    assert member.department_id == (None if role == 'admin' else 'dept_chat')


def test_admin_creates_user_in_department_and_profile_exposes_it(db, member):
    from app.api.v1.users import get_current_user_info
    operator = SimpleNamespace(user_id='operator', username='operator', role=UserRole.admin)
    created = asyncio.run(admin.create_user(AdminUserCreate(username='new_member', email='new_member@example.com',
        password='0' * 64, department_id='dept_chat'), request('POST'), db, operator))
    assert created.department_id == 'dept_chat'
    user = db.query(User).filter_by(user_id=created.user_id).one()
    profile = asyncio.run(get_current_user_info(user, db))
    assert (profile.department_id, profile.department_name, profile.department_status) == ('dept_chat', '日常使用', 'active')


def test_export_labels_web_usage_without_project_or_key(db, member):
    db.add(UsageLog(log_id='web-export', user_id=member.user_id, key_id=None, project_id=None,
        department_id='dept_chat', model='priced', total_tokens=42, cost_cny=Decimal('0.082'), status_code=200))
    db.commit()
    from datetime import datetime
    today = datetime.utcnow().strftime('%Y-%m-%d')
    response = asyncio.run(admin.export_admin_usage(today, today, None, None, None, None, None, None, member, db))
    async def content():
        return ''.join([chunk async for chunk in response.body_iterator])
    csv = asyncio.run(content())
    assert '无项目' in csv and '网页对话' in csv and '日常使用' in csv
    assert '0.08200000' in csv
