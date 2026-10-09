import asyncio
from types import SimpleNamespace
from unittest.mock import patch

import httpx
import pytest

from app.models.channel import ChannelType
from app.services.sync_service import QuotaSyncService, QuotaSyncError, normalize_quota_windows


@pytest.mark.parametrize('endpoint', ['https://api.deepseek.com', 'https://api.deepseek.com/v1/'])
def test_deepseek_balance_request(endpoint):
    channel = SimpleNamespace(type=ChannelType.deepseek, endpoint=endpoint, api_key='test-key')
    adapter = QuotaSyncService(None).get_adapter(channel)
    assert adapter is not None
    payload = {'is_available': True, 'balance_infos': [
        {'currency': 'CNY', 'total_balance': '12.3456', 'granted_balance': '2.0000', 'topped_up_balance': '10.3456'},
        {'currency': 'USD', 'total_balance': '0.0010', 'granted_balance': '0', 'topped_up_balance': '0.0010'},
    ]}

    def handle(request):
        assert str(request.url) == 'https://api.deepseek.com/user/balance'
        assert request.method == 'GET'
        assert request.headers['Authorization'] == 'Bearer test-key'
        assert request.headers['Accept'] == 'application/json'
        return httpx.Response(200, json=payload)

    client = httpx.AsyncClient(transport=httpx.MockTransport(handle))
    with patch('app.services.sync_service.httpx.AsyncClient', return_value=client):
        result = asyncio.run(adapter.fetch_quota())
    windows = normalize_quota_windows(result['windows'])
    assert windows[0]['raw_data'] == payload
    assert result['raw_data'] == payload


@pytest.mark.parametrize('status,payload', [(401, {'error': {'message': 'invalid key'}}), (200, {}), (200, {'balance_infos': []})])
def test_deepseek_failure_is_not_zero_balance(status, payload):
    channel = SimpleNamespace(type=ChannelType.deepseek, endpoint='https://api.deepseek.com', api_key='test-key')
    adapter = QuotaSyncService(None).get_adapter(channel)
    assert adapter is not None
    client = httpx.AsyncClient(transport=httpx.MockTransport(lambda request: httpx.Response(status, json=payload)))
    with patch('app.services.sync_service.httpx.AsyncClient', return_value=client):
        with pytest.raises(QuotaSyncError):
            asyncio.run(adapter.fetch_quota())
