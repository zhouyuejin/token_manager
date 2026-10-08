"""标准 /v1 入口复用代理认证和模型权限，供 CC Switch 自动发现模型。"""
import pytest
from fastapi.testclient import TestClient

import app.middleware as proxy_middleware
from app.core.database import get_db
from app.main import app
from app.models.api_key import ApiKey
from app.models.channel import Channel, ChannelType
from app.models.model import Model
from app.models.model_channel import ModelChannel
from app.models.model_group import ModelGroup
from app.models.user import User


@pytest.fixture
def proxy_client(db, SessionLocal, monkeypatch):
    user = User(user_id='v1_user', username='v1_user', email='v1@example.com', password='hash')
    key = ApiKey(key_id='v1_key', user_id=user.user_id, api_key='tmk_v1_test')
    group = ModelGroup(group_id='v1_default', name='default', is_default=1)
    channel = Channel(channel_id='v1_channel', name='test', type=ChannelType.openai,
                      endpoint='https://example.invalid', api_key='unused')
    visible = Model(model_id='visible-model', display_name='Visible', model_groups=[group])
    hidden = Model(model_id='hidden-model')
    db.add_all([user, key, group, channel, visible, hidden])
    db.flush()
    for model in (visible, hidden):
        db.add(ModelChannel(model_id=model.model_id, channel_id=channel.channel_id,
                            upstream_model=model.model_id))
    db.commit()
    monkeypatch.setattr(proxy_middleware, 'SessionLocal', SessionLocal)
    monkeypatch.setitem(app.dependency_overrides, get_db, lambda: db)
    return TestClient(app)


@pytest.mark.parametrize('prefix', ['/v1', '/api/v1/proxy'])
def test_model_discovery_returns_only_accessible_models(proxy_client, prefix):
    response = proxy_client.get(prefix + '/models', headers={
        'Authorization': 'Bearer tmk_v1_test', 'X-Request-ID': 'model-discovery',
    })
    assert response.status_code == 200, response.text
    assert response.json()['object'] == 'list'
    assert [model['id'] for model in response.json()['data']] == ['visible-model']
    assert response.headers['X-Request-ID'] == 'model-discovery'


@pytest.mark.parametrize('path', ['/v1/models', '/api/v1/proxy/models'])
def test_model_discovery_requires_api_key(path):
    response = TestClient(app).get(path)
    assert response.status_code == 401, response.text
    assert response.headers['X-Request-ID'].startswith('req_')


@pytest.mark.parametrize('prefix', ['/v1', '/api/v1/proxy'])
def test_model_discovery_rejects_invalid_api_key(proxy_client, prefix):
    response = proxy_client.get(prefix + '/models', headers={
        'Authorization': 'Bearer invalid-key',
    })
    assert response.status_code == 401, response.text
    assert response.json()['detail'] == '无效的API Key'


@pytest.mark.parametrize('prefix', ['/v1', '/api/v1/proxy'])
def test_responses_uses_same_auth_and_validation(proxy_client, prefix):
    response = proxy_client.post(prefix + '/responses', json={})
    assert response.status_code == 401, response.text
    response = proxy_client.post(prefix + '/responses', json={}, headers={
        'Authorization': 'Bearer tmk_v1_test',
    })
    assert response.status_code == 422, response.text
    assert response.json()['detail'] == '缺少 model'
