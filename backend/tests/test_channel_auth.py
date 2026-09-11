"""测试认证 Header 构建器"""
import pytest
from unittest.mock import MagicMock
from app.models.channel import Channel, ChannelType, AuthType, UpstreamFormat
from app.services.channel_auth import build_auth_headers, get_upstream_url


def _channel(type_="openai", auth_type="auto", upstream_format="auto", auth_headers=None):
    ch = MagicMock(spec=Channel)
    ch.type = ChannelType(type_)
    ch.auth_type = auth_type
    ch.upstream_format = upstream_format
    ch.auth_headers = auth_headers
    ch.endpoint = "https://api.example.com"
    return ch


def test_auto_infers_bearer_for_openai():
    ch = _channel(type_="openai")
    headers = build_auth_headers(ch, "sk-test")
    assert headers["Authorization"] == "Bearer sk-test"
    assert "x-api-key" not in headers


def test_auto_infers_api_key_for_anthropic():
    ch = _channel(type_="anthropic")
    headers = build_auth_headers(ch, "sk-ant-test")
    assert headers.get("x-api-key") == "sk-ant-test"
    assert "Authorization" not in headers


def test_auto_infers_azure_api_key():
    ch = _channel(type_="azure")
    headers = build_auth_headers(ch, "azure-key")
    assert headers.get("api-key") == "azure-key"


def test_auto_infers_bearer_for_google():
    ch = _channel(type_="google")
    headers = build_auth_headers(ch, "google-key")
    assert headers["Authorization"] == "Bearer google-key"


def test_explicit_bearer_used_for_anthropic():
    ch = _channel(type_="anthropic", auth_type="bearer")
    headers = build_auth_headers(ch, "sk-test")
    assert headers["Authorization"] == "Bearer sk-test"


def test_explicit_api_key_used_for_openai():
    ch = _channel(type_="openai", auth_type="api_key")
    headers = build_auth_headers(ch, "sk-test")
    assert headers.get("x-api-key") == "sk-test"


def test_auth_headers_merged_into_result():
    ch = _channel(
        type_="anthropic",
        auth_headers={"anthropic-version": "2023-06-01"}
    )
    headers = build_auth_headers(ch, "sk-ant")
    assert headers["x-api-key"] == "sk-ant"
    assert headers["anthropic-version"] == "2023-06-01"


def test_auth_headers_cannot_override_main_auth():
    ch = _channel(
        type_="openai",
        auth_headers={"Authorization": "Bearer hacker"}
    )
    headers = build_auth_headers(ch, "sk-real")
    assert headers["Authorization"] == "Bearer sk-real"


def test_get_upstream_url_chat_default():
    ch = _channel(type_="openai", upstream_format="chat")
    url = get_upstream_url(ch)
    assert url == "https://api.example.com/v1/chat/completions"


def test_get_upstream_url_anthropic():
    ch = _channel(type_="anthropic", upstream_format="anthropic")
    url = get_upstream_url(ch)
    assert url == "https://api.example.com/v1/messages"


def test_get_upstream_url_auto_infers():
    ch = _channel(type_="anthropic", upstream_format="auto")
    url = get_upstream_url(ch)
    assert url == "https://api.example.com/v1/messages"


def test_get_upstream_url_azure_uses_chat():
    ch = _channel(type_="azure", upstream_format="chat")
    url = get_upstream_url(ch)
    assert url == "https://api.example.com/v1/chat/completions"


def test_get_upstream_url_strips_trailing_slash():
    ch = _channel(type_="openai", upstream_format="chat")
    ch.endpoint = "https://api.example.com/"
    url = get_upstream_url(ch)
    assert url == "https://api.example.com/v1/chat/completions"


def test_query_key_returns_empty_auth_headers():
    ch = _channel(type_="custom", auth_type="query_key")
    headers = build_auth_headers(ch, "key123")
    assert "Authorization" not in headers
    assert "x-api-key" not in headers
