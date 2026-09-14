import pytest
import httpx

from app.models.channel import Channel, ChannelType
from app.services.model_sync_service import ModelSyncService, OpenAIModelAdapter


def _openai_channel(endpoint: str = "https://api.example.com/v1") -> Channel:
    return Channel(
        channel_id="ch_test",
        name="openai",
        type=ChannelType.openai,
        endpoint=endpoint,
        api_key="sk-test",
    )


def _patch_async_client(monkeypatch, transport: httpx.MockTransport):
    original = httpx.AsyncClient

    class AsyncClientWithTransport(original):
        def __init__(self, *args, **kwargs):
            kwargs["transport"] = transport
            super().__init__(*args, **kwargs)

    monkeypatch.setattr(httpx, "AsyncClient", AsyncClientWithTransport)


@pytest.mark.asyncio
async def test_openai_model_sync_strips_endpoint_whitespace_and_uses_models_path(monkeypatch):
    seen_urls = []

    def handle(request: httpx.Request) -> httpx.Response:
        seen_urls.append(str(request.url))
        return httpx.Response(200, json={"data": [{"id": "gpt-5.6-sol"}]})

    _patch_async_client(monkeypatch, httpx.MockTransport(handle))

    models = await OpenAIModelAdapter(_openai_channel(" https://api.example.com/v1 ")).fetch_models()

    assert seen_urls == ["https://api.example.com/v1/models"]
    assert [m.to_dict() for m in models] == [
        {"model_id": "gpt-5.6-sol", "name": "gpt-5.6-sol", "owned_by": "openai"}
    ]


@pytest.mark.asyncio
async def test_openai_model_sync_failure_does_not_return_stale_default_models(monkeypatch):
    _patch_async_client(
        monkeypatch,
        httpx.MockTransport(lambda request: httpx.Response(500, json={"error": "boom"})),
    )

    result = await ModelSyncService(db=None).sync_channel_models(_openai_channel())

    assert result["success"] is False
    assert result["count"] == 0
    assert result["models"] == []
