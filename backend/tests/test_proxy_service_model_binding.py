"""
测试 ProxyService.check_model_group_access 在"分组绑定模型"语义下的行为。

数据库：MySQL token_db_test（与生产一致）。

覆盖 §11.1 中的权限相关规则：
- 同一供应商两个模型可分别授权
- 用户只绑定 gpt-4o-mini 时不可访问 gpt-4o
- 模型属多分组时任一有效分组即放行
- 默认分组模型对所有用户可用
- 用户额外分组模型可用
- disabled 分组中的模型不可用
- disabled 模型不可用，重新启用可恢复
- disabled 供应商下模型不可用
- 未绑定任何有效分组的模型不可用
- 错误消息不泄露分组结构
"""
import pytest
import json
from sqlalchemy.orm import Session

import app.models  # noqa: F401, E402
from app.models.user import User, UserRole, UserStatus
from app.models.api_key import ApiKey, ApiKeyStatus
from app.models.model_group import ModelGroup, ModelGroupStatus
from app.models.provider import Provider, ProviderType, ProviderStatus
from app.models.model_mapping import ModelMapping, ModelMappingStatus
from app.services.proxy_service import ProxyService
# db fixture 由 conftest.py 提供（MySQL）


# ========== Fixtures ==========

@pytest.fixture
def default_group(db: Session) -> ModelGroup:
    g = ModelGroup(group_id="grp_default", name="默认", status=ModelGroupStatus.active, is_default=1)
    db.add(g)
    db.commit()
    db.refresh(g)
    return g


@pytest.fixture
def extra_group(db: Session) -> ModelGroup:
    g = ModelGroup(group_id="grp_extra", name="额外", status=ModelGroupStatus.active, is_default=0)
    db.add(g)
    db.commit()
    db.refresh(g)
    return g


@pytest.fixture
def disabled_group(db: Session) -> ModelGroup:
    g = ModelGroup(group_id="grp_disabled", name="禁用分组", status=ModelGroupStatus.disabled, is_default=0)
    db.add(g)
    db.commit()
    db.refresh(g)
    return g


@pytest.fixture
def provider_a(db: Session) -> Provider:
    p = Provider(provider_id="prov_a", name="A", type=ProviderType.openai,
                 endpoint="https://a/", api_key="k", status=ProviderStatus.active)
    db.add(p)
    db.commit()
    db.refresh(p)
    return p


@pytest.fixture
def disabled_provider(db: Session) -> Provider:
    p = Provider(provider_id="prov_disabled", name="D", type=ProviderType.openai,
                 endpoint="https://d/", api_key="k", status=ProviderStatus.disabled)
    db.add(p)
    db.commit()
    db.refresh(p)
    return p


@pytest.fixture
def gpt4o(db: Session, provider_a: Provider) -> ModelMapping:
    m = ModelMapping(model_id="gpt-4o", provider_id=provider_a.provider_id,
                     provider_model="gpt-4o", status=ModelMappingStatus.active)
    db.add(m)
    db.commit()
    db.refresh(m)
    return m


@pytest.fixture
def gpt4o_mini(db: Session, provider_a: Provider) -> ModelMapping:
    m = ModelMapping(model_id="gpt-4o-mini", provider_id=provider_a.provider_id,
                     provider_model="gpt-4o-mini", status=ModelMappingStatus.active)
    db.add(m)
    db.commit()
    db.refresh(m)
    return m


@pytest.fixture
def unbound_model(db: Session, provider_a: Provider) -> ModelMapping:
    m = ModelMapping(model_id="unbound", provider_id=provider_a.provider_id,
                     provider_model="unbound", status=ModelMappingStatus.active)
    db.add(m)
    db.commit()
    db.refresh(m)
    return m


@pytest.fixture
def user_no_groups(db: Session) -> User:
    u = User(user_id="u1", username="u1", email="u1@x", password="h",
             role=UserRole.user, status=UserStatus.active, model_group_ids=None)
    db.add(u)
    db.commit()
    db.refresh(u)
    return u


@pytest.fixture
def user_extra_group(db: Session) -> User:
    u = User(user_id="u2", username="u2", email="u2@x", password="h",
             role=UserRole.user, status=UserStatus.active,
             model_group_ids=json.dumps(["grp_extra"]))
    db.add(u)
    db.commit()
    db.refresh(u)
    return u


@pytest.fixture
def api_key(db: Session, user_no_groups: User) -> ApiKey:
    k = ApiKey(key_id="key1", user_id=user_no_groups.user_id, api_key="tmk1",
               key_name="K", status=ApiKeyStatus.active)
    db.add(k)
    db.commit()
    db.refresh(k)
    return k


# ========== §11.1 权限规则测试 ==========

def test_two_models_can_be_authorized_independently(db, default_group, extra_group, provider_a,
                                                   gpt4o, gpt4o_mini,
                                                   user_extra_group, api_key):
    """同一供应商的两个模型分别授权到不同分组"""
    gpt4o_mini.model_groups.append(default_group)
    gpt4o.model_groups.append(extra_group)
    db.commit()

    # 默认分组用户（user_no_groups）能访问 gpt-4o-mini，不能访问 gpt-4o
    svc = ProxyService(db)
    assert svc.check_model_group_access(api_key, db.query(User).filter_by(user_id="u1").one(), "gpt-4o-mini")["allowed"] is True
    assert svc.check_model_group_access(api_key, db.query(User).filter_by(user_id="u1").one(), "gpt-4o")["allowed"] is False


def test_user_with_only_mini_group_cannot_access_4o(db, default_group, extra_group, provider_a,
                                                    gpt4o, gpt4o_mini, api_key):
    """用户只有 gpt-4o-mini 所在的分组 → 不能访问 gpt-4o"""
    gpt4o_mini.model_groups.append(default_group)
    gpt4o.model_groups.append(extra_group)
    db.commit()

    u = User(user_id="u_only_mini", username="uom", email="uom@x", password="h",
             role=UserRole.user, status=UserStatus.active,
             model_group_ids=json.dumps(["grp_default"]))  # 只有 default 分组
    db.add(u); db.commit()
    api_key2 = ApiKey(key_id="key2", user_id="u_only_mini", api_key="tmk2",
                      key_name="K2", status=ApiKeyStatus.active)
    db.add(api_key2); db.commit()

    svc = ProxyService(db)
    assert svc.check_model_group_access(api_key2, u, "gpt-4o-mini")["allowed"] is True
    assert svc.check_model_group_access(api_key2, u, "gpt-4o")["allowed"] is False


def test_model_in_multiple_groups_any_grants(db, default_group, extra_group, disabled_group, provider_a,
                                             user_no_groups, user_extra_group, gpt4o, api_key):
    """一个模型属于多个分组时，拥有任一有效分组即可访问"""
    gpt4o.model_groups.extend([default_group, extra_group, disabled_group])
    db.commit()

    svc = ProxyService(db)
    # default 用户：grp_default 是有效的 → 放行
    assert svc.check_model_group_access(api_key, user_no_groups, "gpt-4o")["allowed"] is True
    # extra 用户：grp_extra 是有效的 → 放行
    api_key2 = ApiKey(key_id="key3", user_id="u2", api_key="tmk3",
                      key_name="K3", status=ApiKeyStatus.active)
    db.add(api_key2); db.commit()
    assert svc.check_model_group_access(api_key2, user_extra_group, "gpt-4o")["allowed"] is True


def test_default_group_model_available_to_all_users(db, default_group, provider_a,
                                                   gpt4o_mini, user_no_groups, api_key):
    """默认分组中的模型对所有普通用户可用"""
    gpt4o_mini.model_groups.append(default_group)
    db.commit()

    svc = ProxyService(db)
    assert svc.check_model_group_access(api_key, user_no_groups, "gpt-4o-mini")["allowed"] is True


def test_user_extra_group_model_available(db, extra_group, provider_a, gpt4o,
                                          user_extra_group):
    """用户额外分组中的模型对该用户可用"""
    gpt4o.model_groups.append(extra_group)
    db.commit()

    api_key2 = ApiKey(key_id="key4", user_id="u2", api_key="tmk4",
                      key_name="K4", status=ApiKeyStatus.active)
    db.add(api_key2); db.commit()

    svc = ProxyService(db)
    assert svc.check_model_group_access(api_key2, user_extra_group, "gpt-4o")["allowed"] is True


def test_disabled_group_model_unavailable(db, default_group, extra_group, disabled_group,
                                          provider_a, gpt4o, user_no_groups, api_key):
    """disabled 分组中的模型不可用"""
    gpt4o.model_groups.append(disabled_group)
    db.commit()

    svc = ProxyService(db)
    result = svc.check_model_group_access(api_key, user_no_groups, "gpt-4o")
    assert result["allowed"] is False


def test_disabled_model_unavailable_but_recoverable(db, default_group, provider_a,
                                                    gpt4o_mini, user_no_groups, api_key):
    """disabled 模型不可用；重新启用后恢复可用"""
    gpt4o_mini.model_groups.append(default_group)
    db.commit()

    svc = ProxyService(db)
    assert svc.check_model_group_access(api_key, user_no_groups, "gpt-4o-mini")["allowed"] is True

    gpt4o_mini.status = ModelMappingStatus.disabled
    db.commit()
    assert svc.check_model_group_access(api_key, user_no_groups, "gpt-4o-mini")["allowed"] is False

    gpt4o_mini.status = ModelMappingStatus.active
    db.commit()
    assert svc.check_model_group_access(api_key, user_no_groups, "gpt-4o-mini")["allowed"] is True


def test_disabled_provider_model_unavailable(db, default_group, disabled_provider, api_key, user_no_groups):
    """disabled 供应商下模型不可用"""
    m = ModelMapping(model_id="m-on-disabled-prov", provider_id="prov_disabled",
                     provider_model="m", status=ModelMappingStatus.active)
    db.add(m); db.commit()
    g = db.query(ModelGroup).filter_by(group_id="grp_default").one()
    m.model_groups.append(g)
    db.commit()

    svc = ProxyService(db)
    result = svc.check_model_group_access(api_key, user_no_groups, "m-on-disabled-prov")
    assert result["allowed"] is False


def test_unbound_model_unavailable(db, default_group, provider_a, unbound_model,
                                   user_no_groups, api_key):
    """未绑定任何有效分组的模型不可用"""
    svc = ProxyService(db)
    result = svc.check_model_group_access(api_key, user_no_groups, "unbound")
    assert result["allowed"] is False


def test_error_message_does_not_leak_group_structure(db, default_group, provider_a,
                                                     unbound_model, user_no_groups, api_key):
    """错误消息不泄露分组内部结构（§11.1 GC-3）"""
    svc = ProxyService(db)
    result = svc.check_model_group_access(api_key, user_no_groups, "unbound")
    msg = result["message"]
    assert "default" not in msg.lower()
    assert "分组" not in msg
    assert "group" not in msg.lower()
    assert "grp" not in msg.lower()
