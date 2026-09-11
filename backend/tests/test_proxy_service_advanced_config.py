"""测试 ProxyService 使用新配置路由"""
import pytest
from unittest.mock import MagicMock
from app.models.channel import Channel, ChannelType
from app.services.channel_auth import build_auth_headers, get_upstream_url


def _channel(type_="anthropic", upstream_format="auto", auth_type="auto", auth_headers=None):
    ch = MagicMock(spec=Channel)
    ch.channel_id = "ch_test"
    ch.type = ChannelType(type_)
    ch.upstream_format = upstream_format
    ch.auth_type = auth_type
    ch.auth_headers = auth_headers
    ch.endpoint = "https://api.example.com"
    ch.api_key = "test-key-123"
    return ch


def test_anthropic_channel_uses_messages_endpoint():
    ch = _channel(type_="anthropic")
    url = get_upstream_url(ch)
    headers = build_auth_headers(ch, "sk-ant-test")
    assert url == "https://api.example.com/v1/messages"
    assert headers["x-api-key"] == "sk-ant-test"
    assert "Authorization" not in headers


def test_openai_channel_uses_chat_completions():
    ch = _channel(type_="openai", upstream_format="chat")
    url = get_upstream_url(ch)
    headers = build_auth_headers(ch, "sk-test")
    assert url == "https://api.example.com/v1/chat/completions"
    assert headers["Authorization"] == "Bearer sk-test"


def test_gemini_channel_uses_generate_content():
    ch = _channel(type_="google", upstream_format="gemini")
    url = get_upstream_url(ch, model="gemini-1.5-pro")
    assert "gemini-1.5-pro" in url
    assert "generateContent" in url


def test_explicit_format_overrides_type():
    ch = _channel(type_="openai", upstream_format="anthropic")
    url = get_upstream_url(ch)
    assert url == "https://api.example.com/v1/messages"


def test_anthropic_with_extra_headers():
    ch = _channel(type_="anthropic", auth_headers={"anthropic-version": "2023-06-01"})
    headers = build_auth_headers(ch, "sk-ant")
    assert headers["anthropic-version"] == "2023-06-01"
    assert headers["x-api-key"] == "sk-ant"
