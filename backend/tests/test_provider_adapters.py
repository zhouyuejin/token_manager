import json
import httpx
from unittest.mock import MagicMock

from app.models.channel import Channel, ChannelType, UpstreamFormat
from app.services import proxy_service
from app.services.provider_adapters import (
    AnthropicAdapter,
    ProviderAdapter,
    _ADAPTERS,
    get_provider_adapter,
)


def _channel(type_, upstream_format="auto"):
    channel = MagicMock(spec=Channel)
    channel.type = ChannelType(type_)
    channel.upstream_format = upstream_format
    channel.auth_type = "auto"
    channel.auth_headers = None
    channel.endpoint = "https://api.example.com/v1"
    channel.timeout = 5
    return channel


def test_anthropic_adapter_keeps_auto_format_behavior():
    channel = _channel("anthropic")

    adapter = get_provider_adapter(channel)

    assert isinstance(adapter, AnthropicAdapter)
    assert adapter.build_url(channel) == "https://api.example.com/v1/messages"
    assert adapter.build_headers(channel, "sk-ant") == {
        "x-api-key": "sk-ant",
        "anthropic-version": "2023-06-01",
    }
    assert channel.upstream_format == "auto"


def test_anthropic_adapter_converts_chat_request_and_response():
    adapter = AnthropicAdapter()
    request = adapter.transform_request({
        "messages": [
            {"role": "system", "content": "Be concise"},
            {"role": "user", "content": "Hello"},
        ],
        "max_tokens": 32,
        "stop": ["END"],
    }, "claude-test")

    assert request == {
        "model": "claude-test",
        "max_tokens": 32,
        "messages": [{"role": "user", "content": "Hello"}],
        "system": "Be concise",
        "stop_sequences": ["END"],
    }
    assert adapter.transform_response({
        "id": "msg_1", "model": "claude-test", "content": [{"type": "text", "text": "Hi"}],
        "stop_reason": "end_turn", "usage": {"input_tokens": 2, "output_tokens": 1},
    })["usage"] == {"prompt_tokens": 2, "completion_tokens": 1, "total_tokens": 3}


def test_gemini_adapter_converts_chat_request_and_response():
    from app.services.provider_adapters import GeminiAdapter

    adapter = GeminiAdapter()
    request = adapter.transform_request({
        "messages": [{"role": "system", "content": "Be concise"},
                     {"role": "assistant", "content": "Hello"},
                     {"role": "user", "content": "Again"}],
        "max_tokens": 16,
    }, "gemini-test")
    assert request == {
        "contents": [
            {"role": "model", "parts": [{"text": "Hello"}]},
            {"role": "user", "parts": [{"text": "Again"}]},
        ],
        "system_instruction": {"parts": [{"text": "Be concise"}]},
        "generationConfig": {"maxOutputTokens": 16},
    }
    response = adapter.transform_response({
        "candidates": [{"content": {"parts": [{"text": "Done"}]}, "finishReason": "STOP"}],
        "usageMetadata": {"promptTokenCount": 3, "candidatesTokenCount": 2, "totalTokenCount": 5},
    })
    assert response["choices"][0]["message"]["content"] == "Done"
    assert response["usage"]["total_tokens"] == 5


def test_anthropic_adapter_converts_stream_events():
    adapter = AnthropicAdapter()
    start = adapter.transform_stream_line('data: ' + json.dumps({
        "type": "message_start", "message": {"id": "msg_1", "model": "claude-test",
        "usage": {"input_tokens": 3}},
    }))
    delta = adapter.transform_stream_line('data: ' + json.dumps({
        "type": "content_block_delta", "delta": {"type": "text_delta", "text": "Hi"},
    }))
    finish = adapter.transform_stream_line('data: ' + json.dumps({
        "type": "message_delta", "delta": {"stop_reason": "end_turn"},
        "usage": {"output_tokens": 2},
    }))

    assert json.loads(start[0][6:])["choices"][0]["delta"] == {"role": "assistant"}
    assert json.loads(delta[0][6:])["choices"][0]["delta"] == {"content": "Hi"}
    assert json.loads(finish[0][6:])["usage"] == {
        "prompt_tokens": 3, "completion_tokens": 2, "total_tokens": 5,
    }
    assert adapter.transform_stream_line('data: ' + json.dumps({"type": "message_stop"})) == ["data: [DONE]"]


def test_proxy_service_uses_registered_adapter_for_request_and_response(monkeypatch):
    observed = {}

    class TestAdapter(ProviderAdapter):
        def build_url(self, channel, model=None):
            return "https://adapter.example/test"

        def build_headers(self, channel, api_key):
            return {"X-Adapter": "used"}

        def transform_request(self, request_data, upstream_model):
            observed["model"] = upstream_model
            return {"adapted_request": request_data["messages"]}

        def transform_response(self, response_data):
            return {**response_data, "adapted": True}

    monkeypatch.setitem(_ADAPTERS, UpstreamFormat.responses, TestAdapter())
    channel = _channel("openai", "responses")
    original_client = httpx.Client

    def handle(request):
        observed["url"] = str(request.url)
        observed["headers"] = request.headers
        observed["body"] = request.read()
        return httpx.Response(200, json={"ok": True})

    monkeypatch.setattr(
        proxy_service.httpx,
        "Client",
        lambda **kwargs: original_client(transport=httpx.MockTransport(handle), **kwargs),
    )
    result = proxy_service.ProxyService(db=None)._forward_one(
        channel, "upstream-model", "key", {"messages": [{"role": "user", "content": "hi"}]},
    )

    assert result["success"] is True
    assert result["data"] == {"ok": True, "adapted": True}
    assert observed["model"] == "upstream-model"
    assert observed["url"] == "https://adapter.example/test"
    assert observed["headers"]["x-adapter"] == "used"
    assert json.loads(observed["body"]) == {
        "adapted_request": [{"role": "user", "content": "hi"}],
    }
