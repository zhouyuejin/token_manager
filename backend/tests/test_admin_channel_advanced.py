"""测试 admin API 正确处理新字段

Schema 层契约 (字段定义、校验、默认值) 已由
test_channel_advanced_config_schema.py 覆盖;此处聚焦 admin.py 的
序列化/反序列化语义。
"""
from app.schemas.admin import ChannelCreate, ChannelUpdate


def test_schema_to_dict_for_persistence():
    """schema 转 dict 后字段完整,可直接传给 ORM Channel(...)"""
    s = ChannelCreate(
        name="test",
        type="anthropic",
        endpoint="https://api.anthropic.com",
        api_key="sk",
        upstream_format="anthropic",
        auth_type="api_key",
        auth_headers={"anthropic-version": "2023-06-01"},
    )
    d = s.model_dump()
    assert d["upstream_format"] == "anthropic"
    assert d["auth_type"] == "api_key"
    assert d["auth_headers"] == {"anthropic-version": "2023-06-01"}


def test_schema_update_partial_persistence():
    """ChannelUpdate 部分更新语义正确,未设置字段不进入 dump"""
    s = ChannelUpdate(upstream_format="gemini")
    d = s.model_dump(exclude_unset=True)
    assert d == {"upstream_format": "gemini"}
