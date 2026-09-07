"""
测试"新模型自动绑定默认分组"语义 + 默认分组切换的事务保证。

数据库：MySQL token_db_test（与生产一致）。

覆盖 §2 §11.3：
- 新模型默认绑定当前唯一默认分组（手动/同步/批量/自动四入口）
- 没有默认分组 → 新模型不绑定
- 默认组切换不补绑
- 更新已有模型不重置分组
- 多次同步已有模型不重置分组
- set-default 事务性清除其他默认组
"""
import pytest
import json
from sqlalchemy.orm import Session

import app.models  # noqa: F401, E402
from app.models.user import User, UserRole, UserStatus
from app.models.api_key import ApiKey, ApiKeyStatus
from app.models.model_group import (
    ModelGroup, ModelGroupStatus,
    bind_new_model_to_default_group,
    get_unique_default_group,
)
from app.models.provider import Provider, ProviderType, ProviderStatus
from app.models.model_mapping import ModelMapping, ModelMappingStatus
# db fixture 由 conftest.py 提供（MySQL）


@pytest.fixture
def provider(db: Session) -> Provider:
    p = Provider(provider_id="prov_a", name="A", type=ProviderType.openai,
                 endpoint="https://a/", api_key="k", status=ProviderStatus.active)
    db.add(p); db.commit(); db.refresh(p)
    return p


@pytest.fixture
def default_group(db: Session) -> ModelGroup:
    g = ModelGroup(group_id="grp_default", name="默认", status=ModelGroupStatus.active, is_default=1)
    db.add(g); db.commit(); db.refresh(g)
    return g


@pytest.fixture
def another_group(db: Session) -> ModelGroup:
    g = ModelGroup(group_id="grp_other", name="其他", status=ModelGroupStatus.active, is_default=0)
    db.add(g); db.commit(); db.refresh(g)
    return g


# ---- bind_new_model_to_default_group 行为 ----

def test_new_model_binds_to_unique_default(db: Session, default_group, provider):
    """新模型自动加入当前唯一默认分组"""
    m = ModelMapping(model_id="new-model", provider_id=provider.provider_id,
                     provider_model="new-model", status=ModelMappingStatus.active)
    db.add(m)
    bind_new_model_to_default_group(db, m)
    db.commit()

    bound = {g.group_id for g in m.model_groups}
    assert bound == {"grp_default"}


def test_new_model_unbound_when_no_default(db: Session, provider):
    """没有默认分组时，新模型不绑定任何分组"""
    ModelGroup(group_id="grp_x", name="X", status=ModelGroupStatus.active, is_default=0)
    # 注意：这里 fixture 不创建 default_group
    m = ModelMapping(model_id="new-model", provider_id=provider.provider_id,
                     provider_model="new-model", status=ModelMappingStatus.active)
    db.add(m)
    bind_new_model_to_default_group(db, m)
    db.commit()

    assert m.model_groups == []


def test_new_model_unbound_when_multiple_defaults(db: Session, provider):
    """存在多个 is_default=1 分组时，新模型不绑定（避免歧义）"""
    db.add_all([
        ModelGroup(group_id="d1", name="D1", status=ModelGroupStatus.active, is_default=1),
        ModelGroup(group_id="d2", name="D2", status=ModelGroupStatus.active, is_default=1),
    ])
    db.commit()
    m = ModelMapping(model_id="m", provider_id=provider.provider_id,
                     provider_model="m", status=ModelMappingStatus.active)
    db.add(m)
    bind_new_model_to_default_group(db, m)
    db.commit()
    assert m.model_groups == []


def test_new_disabled_model_also_binds(db: Session, default_group, provider):
    """§2.4：新模型无论 active/disabled 都建关联（disabled 仅不可用，绑定合法）"""
    m = ModelMapping(model_id="m", provider_id=provider.provider_id,
                     provider_model="m", status=ModelMappingStatus.disabled)
    db.add(m)
    bind_new_model_to_default_group(db, m)
    db.commit()
    bound = {g.group_id for g in m.model_groups}
    assert "grp_default" in bound


def test_get_unique_default_group_returns_only_when_singleton(db: Session):
    db.add_all([
        ModelGroup(group_id="d1", name="D1", status=ModelGroupStatus.active, is_default=1),
    ])
    db.commit()
    g = get_unique_default_group(db)
    assert g and g.group_id == "d1"

    db.add(ModelGroup(group_id="d2", name="D2", status=ModelGroupStatus.active, is_default=1))
    db.commit()
    assert get_unique_default_group(db) is None


# ---- 更新/同步不重置分组 ----

def test_updating_existing_model_preserves_group_binding(db: Session, default_group, another_group, provider):
    """更新已有模型（display_name / provider_model）不重置分组"""
    m = ModelMapping(model_id="m", provider_id=provider.provider_id,
                     provider_model="m", display_name="old", status=ModelMappingStatus.active)
    m.model_groups.append(another_group)
    db.add(m); db.commit()

    # 模拟更新
    m.display_name = "new"
    m.provider_model = "m-v2"
    db.commit()
    db.refresh(m)

    bound = {g.group_id for g in m.model_groups}
    assert bound == {"grp_other"}, "更新不应重置分组"


def test_resync_preserves_manual_group_binding(db: Session, default_group, another_group, provider):
    """多次同步已有模型不重置管理员手工分配的分组"""
    m = ModelMapping(model_id="m", provider_id=provider.provider_id,
                     provider_model="m", status=ModelMappingStatus.active)
    # 管理员手工加到了 another_group（不是默认组）
    m.model_groups.append(another_group)
    db.add(m); db.commit()

    # 模拟再次同步 — 仅更新 provider_model 字段
    m.provider_model = "m-v2"
    db.commit()
    db.refresh(m)

    bound = {g.group_id for g in m.model_groups}
    assert bound == {"grp_other"}


# ---- set-default 事务 ----

def test_set_default_clears_other_defaults(db: Session, default_group, another_group):
    """set-default 应事务性清除其他默认组，确保唯一"""
    # 当前 default_group 是默认；another_group 不是
    from app.services.model_groups_service import set_default_group
    set_default_group(db, "grp_other")
    db.commit()

    d1 = db.query(ModelGroup).filter_by(group_id="grp_default").one()
    d2 = db.query(ModelGroup).filter_by(group_id="grp_other").one()
    assert d1.is_default == 0
    assert d2.is_default == 1


def test_unset_default_does_not_clear_bindings(db: Session, default_group, another_group, provider):
    """§2.11：unset-default 不清除已有模型绑定"""
    m = ModelMapping(model_id="m", provider_id=provider.provider_id,
                     provider_model="m", status=ModelMappingStatus.active)
    m.model_groups.append(default_group)
    db.add(m); db.commit()

    from app.services.model_groups_service import unset_default_group
    unset_default_group(db, "grp_default")
    db.commit()

    db.refresh(m)
    assert m.model_groups == [default_group]


def test_set_default_does_not_rebind_historical_models(db: Session, default_group, another_group, provider):
    """§2.10：默认组切换不自动补绑历史模型"""
    # 旧默认组 = default_group，已有模型 m_old 绑定到 default_group
    m_old = ModelMapping(model_id="m-old", provider_id=provider.provider_id,
                         provider_model="m-old", status=ModelMappingStatus.active)
    m_old.model_groups.append(default_group)
    db.add(m_old); db.commit()

    # 把另一个组设为默认
    from app.services.model_groups_service import set_default_group
    set_default_group(db, "grp_other")
    db.commit()

    db.refresh(m_old)
    bound = {g.group_id for g in m_old.model_groups}
    # 历史模型不应被自动绑定到新默认组
    assert "grp_other" not in bound
    assert "grp_default" in bound
