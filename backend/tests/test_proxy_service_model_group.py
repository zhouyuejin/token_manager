"""测试 ProxyService.get_effective_model_group_ids 和 check_model_group_access

数据库：MySQL token_db_test（与生产一致）。
"""
import pytest
import json
from sqlalchemy.orm import Session

import app.models  # noqa: F401, E402
from app.models.user import User, UserRole, UserStatus
from app.models.api_key import ApiKey, ApiKeyStatus
from app.models.model_group import ModelGroup, ModelGroupStatus
from app.models.model import Model, ModelStatus
from app.models.channel import Channel, ChannelType, ChannelStatus
from app.models.model_channel import ModelChannel
from app.services.proxy_service import ProxyService
# db fixture 由 conftest.py 提供（MySQL）


@pytest.fixture
def active_channel(db: Session) -> Channel:
    channel = Channel(
        channel_id="ch_active", name="Active", type=ChannelType.openai,
        endpoint="https://a/", api_key="k", status=ChannelStatus.active,
    )
    db.add(channel)
    db.commit()
    return channel


@pytest.fixture
def default_active_group(db: Session) -> ModelGroup:
    g = ModelGroup(
        group_id="grp_default",
        name="默认分组",
        status=ModelGroupStatus.active,
        is_default=1,
    )
    db.add(g)
    db.commit()
    db.refresh(g)
    return g


@pytest.fixture
def default_disabled_group(db: Session) -> ModelGroup:
    g = ModelGroup(
        group_id="grp_disabled",
        name="已禁用的默认分组",
        status=ModelGroupStatus.disabled,
        is_default=1,
    )
    db.add(g)
    db.commit()
    db.refresh(g)
    return g


@pytest.fixture
def non_default_active_group(db: Session) -> ModelGroup:
    g = ModelGroup(
        group_id="grp_extra",
        name="额外分组",
        status=ModelGroupStatus.active,
        is_default=0,
    )
    db.add(g)
    db.commit()
    db.refresh(g)
    return g


@pytest.fixture
def model_in_default_group(db: Session, default_active_group: ModelGroup, active_channel) -> Model:
    model = Model(model_id="gpt-4", status=ModelStatus.active, model_groups=[default_active_group])
    db.add(model)
    db.flush()
    db.add(ModelChannel(model_id=model.model_id, channel_id=active_channel.channel_id, upstream_model=model.model_id))
    db.commit()
    return model


@pytest.fixture
def model_in_non_default_group(db: Session, non_default_active_group: ModelGroup, active_channel) -> Model:
    model = Model(model_id="gpt-3.5", status=ModelStatus.active, model_groups=[non_default_active_group])
    db.add(model)
    db.flush()
    db.add(ModelChannel(model_id=model.model_id, channel_id=active_channel.channel_id, upstream_model=model.model_id))
    db.commit()
    return model


@pytest.fixture
def user_no_groups(db: Session) -> User:
    u = User(
        user_id="user_no_groups",
        username="user_no_groups",
        password="hashed",
        email="no_groups@test.com",
        role=UserRole.user,
        status=UserStatus.active,
        model_group_ids="[]",
    )
    db.add(u)
    db.commit()
    db.refresh(u)
    return u


@pytest.fixture
def user_with_extra_group(db: Session) -> User:
    u = User(
        user_id="user_with_extra",
        username="user_with_extra",
        password="hashed",
        email="extra@test.com",
        role=UserRole.user,
        status=UserStatus.active,
        model_group_ids=json.dumps(["grp_extra"]),
    )
    db.add(u)
    db.commit()
    db.refresh(u)
    return u


@pytest.fixture
def api_key(db: Session, user_no_groups: User) -> ApiKey:
    k = ApiKey(
        key_id="key_test_1",
        user_id=user_no_groups.user_id,
        api_key="tmk_test_key_1",
        key_name="Test Key",
        status=ApiKeyStatus.active,
    )
    db.add(k)
    db.commit()
    db.refresh(k)
    return k


# ---- Tests for get_effective_model_group_ids ----

def test_get_effective_default_only(db: Session, default_active_group, user_no_groups):
    """Scenario 1: User has no model_group_ids → effective = default group"""
    service = ProxyService(db)
    effective = service.get_effective_model_group_ids(user_no_groups)
    assert effective == {"grp_default"}


def test_get_effective_default_plus_user(db: Session, default_active_group, non_default_active_group, user_with_extra_group):
    """Scenario 2: User has extra groups + default exists → union"""
    service = ProxyService(db)
    effective = service.get_effective_model_group_ids(user_with_extra_group)
    assert "grp_default" in effective
    assert "grp_extra" in effective
    assert len(effective) == 2


def test_get_effective_disabled_default_excluded(db: Session, default_disabled_group, user_no_groups):
    """Scenario 3: Default group is disabled → excluded from effective"""
    service = ProxyService(db)
    effective = service.get_effective_model_group_ids(user_no_groups)
    assert "grp_disabled" not in effective


def test_get_effective_no_default_returns_empty(db: Session, user_no_groups):
    """Scenario 4: No default group exists → effective = user_ids (empty)"""
    service = ProxyService(db)
    effective = service.get_effective_model_group_ids(user_no_groups)
    assert effective == set()


def test_get_effective_user_null_model_group_ids(db: Session, default_active_group):
    """Null/None model_group_ids treated as empty list"""
    u = User(
        user_id="user_null",
        username="user_null",
        password="hashed",
        email="null@test.com",
        role=UserRole.user,
        status=UserStatus.active,
        model_group_ids=None,
    )
    db.add(u)
    db.commit()
    db.refresh(u)
    service = ProxyService(db)
    effective = service.get_effective_model_group_ids(u)
    assert effective == {"grp_default"}


def test_get_effective_multiple_default_groups(db: Session, user_no_groups):
    """Multiple is_default=1 groups → all included (GC-6)"""
    g1 = ModelGroup(group_id="grp_d1", name="Default 1", status=ModelGroupStatus.active, is_default=1)
    g2 = ModelGroup(group_id="grp_d2", name="Default 2", status=ModelGroupStatus.active, is_default=1)
    db.add_all([g1, g2])
    db.commit()
    service = ProxyService(db)
    effective = service.get_effective_model_group_ids(user_no_groups)
    assert "grp_d1" in effective
    assert "grp_d2" in effective




def test_check_access_denied_no_groups(
    db: Session, non_default_active_group, user_no_groups, api_key,
    model_in_non_default_group
):
    """User has no effective groups and the model belongs to a non-default group → denied"""
    service = ProxyService(db)
    result = service.check_model_group_access(api_key, user_no_groups, "gpt-3.5")
    assert result["allowed"] is False
    assert result["message"] == "当前 Key 未被授权访问该模型"


def test_check_access_denied_no_group_leak(
    db: Session, non_default_active_group, user_no_groups, api_key,
    model_in_non_default_group
):
    """GC-3: Error message must not leak group names when access is denied"""
    service = ProxyService(db)
    result = service.check_model_group_access(api_key, user_no_groups, "gpt-3.5")
    assert result["allowed"] is False
    msg = result["message"]
    assert "default" not in msg.lower()
    assert "分组" not in msg
    assert "group" not in msg.lower()
    assert "grp" not in msg.lower()
    assert "grp_default" not in msg


def test_check_access_model_not_found(
    db: Session, api_key, user_no_groups, model_in_default_group
):
    """Unknown model → denied with generic message"""
    service = ProxyService(db)
    result = service.check_model_group_access(api_key, user_no_groups, "nonexistent-model")
    assert result["allowed"] is False
    assert result["message"] == "当前 Key 未被授权访问该模型"
