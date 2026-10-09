import asyncio
from types import SimpleNamespace

import pytest

from app.services.quota_script import execute_quota_script
from app.services.sync_service import QuotaSyncService
from app.models.channel import ChannelType


def run(script, timeout=15):
    return asyncio.run(execute_quota_script(script, 'https://api.deepseek.com/v1', 'secret-key', timeout=timeout))


def test_script_returns_balance_without_losing_precision():
    assert run('return {balance: {currency: "CNY", total_balance: "12.3456"}};')['balance']['total_balance'] == '12.3456'


def test_script_has_no_system_access_and_redacts_key():
    assert run('return {windows: [{type:"daily",limit:10}], raw_data: [typeof require, typeof process, apiKey]};')['raw_data'] == ['undefined', 'undefined', '***']


@pytest.mark.parametrize('script', ['while(true) {}', 'return {};', 'throw new Error(apiKey);', 'return {windows:[{type:"invalid"}]};'])
def test_invalid_or_stuck_script_fails(script):
    with pytest.raises(ValueError) as error:
        run(script, timeout=1)
    assert 'secret-key' not in str(error.value)


def test_script_mode_works_for_unsupported_provider():
    channel = SimpleNamespace(type=ChannelType.custom, endpoint='https://example.com', api_key='test')
    assert QuotaSyncService(None).get_adapter(channel, {'query_mode':'script', 'script':'return {windows:[]};'}) is not None


def test_worker_http_request_and_deepseek_example(monkeypatch):
    import httpx
    from app.services.quota_script_worker import evaluate
    original_client = httpx.Client

    def handle(request):
        assert str(request.url) == 'https://api.deepseek.com/user/balance'
        assert request.headers['Authorization'] == 'Bearer test'
        return httpx.Response(200, json={'balance_infos': [{'currency': 'CNY', 'total_balance': '1.2345'}]})

    monkeypatch.setattr(httpx, 'Client', lambda **kwargs: original_client(transport=httpx.MockTransport(handle), **kwargs))
    result = evaluate({'endpoint': 'https://api.deepseek.com/v1', 'api_key': 'test', 'script': '''
        const response = http.get('/user/balance', {headers: {Authorization: 'Bearer ' + apiKey}});
        return {balance: response.data.balance_infos[0]};
    '''})
    assert result['balance']['total_balance'] == '1.2345'


@pytest.mark.parametrize('url', ['https://other.example/balance', 'file:///etc/passwd', 'https://api.deepseek.com:444/balance'])
def test_worker_rejects_other_origins(url):
    from app.services.quota_script_worker import evaluate
    with pytest.raises(Exception, match='同源'):
        evaluate({'endpoint': 'https://api.deepseek.com', 'api_key': 'test', 'script': f'http.get({url!r}); return {{windows:[]}};'})


def test_script_configuration_survives_schema_validation():
    from app.schemas.admin import QuotaConfig
    config = QuotaConfig(query_mode='script', script='return {balance:{currency:"USD",total_balance:"1"}};')
    assert config.model_dump()['script'] == config.script


@pytest.mark.parametrize('script', [
    'return {windows:[{type:"daily",limit:-1}]};',
    'return {windows:[{type:"daily",percent:101}]};',
    'return {windows:[{type:"daily",used:1e30}]};',
    'return {windows:[{type:"daily",label:{bad:true}}]};',
])
def test_script_rejects_invalid_quota_values(script):
    with pytest.raises(ValueError):
        run(script)


def test_script_sync_persists_normalized_windows():
    import json
    from unittest.mock import MagicMock
    from app.models.channel_quota import SyncStatus

    channel = SimpleNamespace(type=ChannelType.custom, endpoint='https://example.com', api_key='test',
                              name='Custom supplier', channel_id='ch_script', quota_config=json.dumps({
                                  'query_mode': 'script',
                                  'script': 'return {windows:[{type:"daily",label:"每日",limit:100,used:20}]};',
                              }))
    db = MagicMock()
    db.query.return_value.filter.return_value.first.return_value = None
    assert asyncio.run(QuotaSyncService(db).sync_channel_quota(channel))
    quota = db.add.call_args.args[0]
    assert (quota.quota_limit, quota.quota_used, quota.quota_remain) == (100, 20, 80)
    assert quota.sync_status == SyncStatus.success
    assert json.loads(quota.raw_data)['provider'] == 'script'
    db.commit.assert_called_once()
    db.query.return_value.filter.return_value.delete.assert_called_once()


def test_trial_endpoint_does_not_save():
    from unittest.mock import MagicMock
    from app.api.v1.admin import test_channel_quota_script as trial
    from app.schemas.admin import QuotaConfig

    db = MagicMock()
    db.query.return_value.filter.return_value.first.return_value = SimpleNamespace(endpoint='https://example.com', api_key='test')
    config = QuotaConfig(query_mode='script', script='return {balance:{currency:"USD",total_balance:"0.1234"}};')
    result = asyncio.run(trial('ch_script', config, db, None))
    assert result['balance']['total_balance'] == '0.1234'
    db.add.assert_not_called()
    db.commit.assert_not_called()


def test_script_failure_marks_actual_windows_failed():
    import json
    from unittest.mock import MagicMock
    from app.models.channel_quota import ChannelQuota, QuotaType, SyncStatus
    channel = SimpleNamespace(channel_id='ch_script', quota_config=json.dumps({'query_mode': 'script'}))
    quota = ChannelQuota(channel_id='ch_script', quota_type=QuotaType.custom, sync_status=SyncStatus.success)
    db = MagicMock()
    db.query.return_value.filter.return_value.all.return_value = [quota]
    db.query.return_value.filter.return_value.first.return_value = quota
    QuotaSyncService(db)._mark_sync_failed(channel, 'timeout')
    assert quota.sync_status == SyncStatus.failed
    assert quota.sync_error == 'timeout'
    filters = db.query.return_value.filter.call_args_list
    assert filters[-1].args[1].right.value == QuotaType.custom
