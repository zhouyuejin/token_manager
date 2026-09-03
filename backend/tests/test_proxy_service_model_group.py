"""测试 ProxyService.get_effective_model_group_ids 和 check_model_group_access"""
import pytest
import json
from sqlalchemy import create_engine, event
from sqlalchemy.orm import sessionmaker, Session
from sqlalchemy.pool import StaticPool

import sqlalchemy
from sqlalchemy import Integer, TypeDecorator


class _BigIntegerCompat(TypeDecorator):
    impl = Integer
    cache_ok = True

    def load_dialect_impl(self, dialect):
        if dialect.name in ("mysql", "mariadb"):
            return dialect.type_descriptor(sqlalchemy.BigInteger())
        return dialect.type_descriptor(Integer())


sqlalchemy.BigInteger = _BigIntegerCompat

import app.models  # noqa: F401, E402

_orig_create_engine = create_engine


def _patched_engine(url, **kwargs):
    url_str = str(url)
    if url_str.startswith("sqlite") and ":memory:" in url_str:
        kwargs.setdefault("connect_args", {})
        kwargs["connect_args"].setdefault("check_same_thread", False)
        kwargs.setdefault("poolclass", StaticPool)
    return _orig_create_engine(url, **kwargs)


sqlalchemy.create_engine = _patched_engine

from app.core.database import Base
from app.models.user import User, UserRole, UserStatus
from app.models.api_key import ApiKey, ApiKeyStatus
from app.models.model_group import ModelGroup, ModelGroupStatus
from app.models.provider import Provider, ProviderType, ProviderStatus
from app.models.model_mapping import ModelMapping, ModelMappingStatus
from app.services.proxy_service import ProxyService


_test_engine = create_engine(
    "sqlite:///:memory:",
    connect_args={"check_same_thread": False},
    poolclass=StaticPool,
)
Base.metadata.create_all(bind=_test_engine)
TestingSessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=_test_engine)

_id_counters = {}


def _bind_pk_assigner(model_cls):
    @event.listens_for(model_cls, "before_insert", propagate=True)
    def _assign_pk(mapper, connection, target):
        if getattr(target, "id", None) is not None:
            return
        table = target.__tablename__
        _id_counters[table] = _id_counters.get(table, 0) + 1
        target.id = _id_counters[table]


for cls in [User, ModelGroup, Provider, ModelMapping, ApiKey]:
    _bind_pk_assigner(cls)


@pytest.fixture
def db():
    _id_counters.clear()
    session = TestingSessionLocal()
    for table in reversed(Base.metadata.sorted_tables):
        session.execute(table.delete())
    session.commit()
    try:
        yield session
    finally:
        session.close()


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
def provider_with_group(db: Session, default_active_group: ModelGroup) -> Provider:
    p = Provider(
        provider_id="prov_test",
        name="Test Provider",
        type=ProviderType.openai,
        endpoint="https://api.test.com/v1/chat/completions",
        api_key="sk-test",
        status=ProviderStatus.active,
    )
    p.model_groups.append(default_active_group)
    db.add(p)
    db.commit()
    db.refresh(p)
    return p


@pytest.fixture
def provider_no_default_group(db: Session, non_default_active_group: ModelGroup) -> Provider:
    """Provider linked only to a non-default group (used for denial scenarios)."""
    p = Provider(
        provider_id="prov_no_default",
        name="Provider No Default",
        type=ProviderType.openai,
        endpoint="https://api.test2.com/v1/chat/completions",
        api_key="sk-test2",
        status=ProviderStatus.active,
    )
    p.model_groups.append(non_default_active_group)
    db.add(p)
    db.commit()
    db.refresh(p)
    return p


@pytest.fixture
def model_mapping_for_provider(
    db: Session, provider_with_group: Provider
) -> ModelMapping:
    m = ModelMapping(
        model_id="gpt-4",
        provider_id=provider_with_group.provider_id,
        provider_model="gpt-4",
        status=ModelMappingStatus.active,
    )
    db.add(m)
    db.commit()
    db.refresh(m)
    return m


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


# ---- Tests for check_model_group_access ----

def test_check_access_allowed(
    db: Session, api_key, user_no_groups,
    provider_with_group, model_mapping_for_provider
):
    """User with default group can access model in that group"""
    service = ProxyService(db)
    result = service.check_model_group_access(api_key, user_no_groups, "gpt-4")
    assert result["allowed"] is True


def test_check_access_denied_no_groups(
    db: Session, non_default_active_group, user_no_groups, api_key,
    provider_no_default_group
):
    """User has no effective groups, provider uses non-default group → denied"""
    # Create model mapping for this provider
    m = ModelMapping(
        model_id="gpt-4",
        provider_id=provider_no_default_group.provider_id,
        provider_model="gpt-4",
        status=ModelMappingStatus.active,
    )
    db.add(m)
    db.commit()

    service = ProxyService(db)
    result = service.check_model_group_access(api_key, user_no_groups, "gpt-4")
    assert result["allowed"] is False
    assert result["message"] == "当前 Key 未被授权访问该模型"


def test_check_access_denied_no_group_leak(
    db: Session, non_default_active_group, user_no_groups, api_key,
    provider_no_default_group
):
    """GC-3: Error message must not leak group names when access is denied"""
    m = ModelMapping(
        model_id="gpt-4",
        provider_id=provider_no_default_group.provider_id,
        provider_model="gpt-4",
        status=ModelMappingStatus.active,
    )
    db.add(m)
    db.commit()

    service = ProxyService(db)
    result = service.check_model_group_access(api_key, user_no_groups, "gpt-4")
    assert result["allowed"] is False
    msg = result["message"]
    assert "default" not in msg.lower()
    assert "分组" not in msg
    assert "group" not in msg.lower()
    assert "grp" not in msg.lower()
    assert "grp_default" not in msg


def test_check_access_model_not_found(
    db: Session, api_key, user_no_groups, default_active_group, provider_with_group, model_mapping_for_provider
):
    """Unknown model → denied with generic message"""
    service = ProxyService(db)
    result = service.check_model_group_access(api_key, user_no_groups, "nonexistent-model")
    assert result["allowed"] is False
    assert result["message"] == "当前 Key 未被授权访问该模型"


def test_check_access_user_extra_group_access(
    db: Session, non_default_active_group, user_with_extra_group,
    provider_with_group, model_mapping_for_provider
):
    """User has grp_extra which is linked to provider → access granted"""
    api_key2 = ApiKey(
        key_id="key_test_2",
        user_id=user_with_extra_group.user_id,
        api_key="tmk_test_key_2",
        key_name="Test Key 2",
        status=ApiKeyStatus.active,
    )
    db.add(api_key2)
    db.commit()
    
    provider_with_group.model_groups.append(non_default_active_group)
    db.commit()
    
    service = ProxyService(db)
    result = service.check_model_group_access(api_key2, user_with_extra_group, "gpt-4")
    assert result["allowed"] is True
