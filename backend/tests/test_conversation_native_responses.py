"""Codex tools must reach native Responses channels without Chat conversion."""
import asyncio
import json
from types import SimpleNamespace

import httpx
import pytest

from app.services import conversation_gateway as gateway


@pytest.mark.parametrize('tool', [
    {'type': 'custom', 'name': 'apply_patch', 'format': {'type': 'text'}},
    {'type': 'web_search'},
])
def test_native_responses_preserves_non_function_tools(monkeypatch, tool):
    body = {'model': 'm', 'input': 'hello', 'tools': [tool], 'max_output_tokens': 2048}
    reserved = []
    forwarded = []
    channel = SimpleNamespace(timeout=5, channel_id='c')
    adapter = SimpleNamespace(
        build_headers=lambda *args: {},
        build_protocol_url=lambda *args: 'https://example.invalid/v1/responses',
        transform_protocol_response=lambda data: data,
    )

    async def deduct(*args):
        pass

    service = SimpleNamespace(
        check_model_group_access=lambda *args: {'allowed': True},
        reserve_quota=lambda *args: reserved.append(args[-1]),
        select_candidates=lambda *args: [(channel, SimpleNamespace(upstream_model='upstream'), 'key')],
        calculate_tokens=lambda request, response: response['usage'],
        record_usage=lambda *args, **kwargs: None,
        deduct_quota=deduct,
        release_reservation=lambda: None,
    )
    monkeypatch.setattr('app.services.proxy_service.create_proxy_service', lambda db: service)
    monkeypatch.setattr('app.services.rate_limit_service.get_rate_limit_redis_client', lambda: None)
    monkeypatch.setattr('app.services.rate_limit_service.check_proxy_rate_limit', lambda *args: {'allowed': True})
    monkeypatch.setattr(gateway, 'get_provider_adapter', lambda channel: adapter)
    monkeypatch.setattr(gateway, 'resolve_upstream_format', lambda channel: SimpleNamespace(value='responses'))

    def upstream(request):
        forwarded.append(json.loads(request.content))
        return httpx.Response(200, json={'id': 'r', 'output': [], 'usage': {'input_tokens': 2, 'output_tokens': 3}})

    client = httpx.Client
    monkeypatch.setattr(gateway.httpx, 'Client', lambda **kwargs: client(transport=httpx.MockTransport(upstream), **kwargs))

    async def request_json():
        return body

    request = SimpleNamespace(json=request_json, headers={}, state=SimpleNamespace(
        user=SimpleNamespace(user_id='u'), api_key=SimpleNamespace(key_id='k'), request_id='r'))
    response = asyncio.run(gateway.proxy_conversation(request, None, 'responses'))
    assert response.status_code == 200
    assert forwarded == [{**body, 'model': 'upstream'}]
    assert reserved[0]['max_tokens'] == 2048
    assert 'hello' in str(reserved[0]['messages'])
    assert tool['type'] in str(reserved[0]['messages'])
