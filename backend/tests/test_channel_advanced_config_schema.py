"""
测试 ChannelCreate/Update/Response 三个 Schema 对新字段的支持与校验。
"""
import pytest
from pydantic import ValidationError

from app.schemas.admin import ChannelCreate, ChannelUpdate, ChannelResponse


def test_channel_create_accepts_new_fields():
    """显式传入 3 个新字段应被接受"""
    s = ChannelCreate(
        name="test",
        type="anthropic",
        endpoint="https://api.anthropic.com",
        api_key="sk-ant",
        upstream_format="anthropic",
        auth_type="api_key",
        auth_headers={"anthropic-version": "2023-06-01"},
    )
    assert s.upstream_format == "anthropic"
    assert s.auth_type == "api_key"
    assert s.auth_headers == {"anthropic-version": "2023-06-01"}


def test_channel_create_defaults():
    """不传新字段时使用默认值 chat/auto/None"""
    s = ChannelCreate(
        name="test",
        type="openai",
        endpoint="https://api.openai.com",
        api_key="sk",
    )
    assert s.upstream_format == "chat"
    assert s.auth_type == "auto"
    assert s.auth_headers is None


def test_channel_update_partial():
    """ChannelUpdate 只更新部分字段,其他保持 None"""
    s = ChannelUpdate(upstream_format="gemini")
    assert s.upstream_format == "gemini"
    assert s.auth_type is None
    assert s.auth_headers is None


def test_invalid_upstream_format_rejected():
    """非法 upstream_format 应抛出 ValidationError"""
    with pytest.raises(ValidationError):
        ChannelCreate(
            name="test",
            type="openai",
            endpoint="x",
            api_key="k",
            upstream_format="not-a-real-format",
        )


def test_response_has_new_fields():
    """ChannelResponse 应暴露 3 个新字段"""
    fields = ChannelResponse.model_fields
    assert "upstream_format" in fields
    assert "auth_type" in fields
    assert "auth_headers" in fields
