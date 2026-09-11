"""测试 Channel 模型新字段 (upstream_format / auth_type / auth_headers)。"""
from app.models.channel import Channel, ChannelType, AuthType, UpstreamFormat


def test_upstream_format_enum_values():
    assert UpstreamFormat.auto.value == "auto"
    assert UpstreamFormat.chat.value == "chat"
    assert UpstreamFormat.anthropic.value == "anthropic"
    assert UpstreamFormat.gemini.value == "gemini"
    assert UpstreamFormat.responses.value == "responses"
    assert UpstreamFormat.custom.value == "custom"


def test_auth_type_enum_values():
    assert AuthType.auto.value == "auto"
    assert AuthType.bearer.value == "bearer"
    assert AuthType.api_key.value == "api_key"
    assert AuthType.azure_api_key.value == "azure_api_key"
    assert AuthType.query_key.value == "query_key"


def test_channel_has_new_columns():
    columns = Channel.__table__.columns
    assert "upstream_format" in columns
    assert "auth_type" in columns
    assert "auth_headers" in columns


def test_channel_default_values():
    col = Channel.__table__.columns["upstream_format"]
    assert col.default.arg == "chat"
    col = Channel.__table__.columns["auth_type"]
    assert col.default.arg == "auto"
