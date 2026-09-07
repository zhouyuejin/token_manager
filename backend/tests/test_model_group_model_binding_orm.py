"""
测试 ModelGroup 与 ModelMapping 的多对多关系（新 ORM）。

数据库：MySQL token_db_test（与生产一致）。
覆盖 §4.1：ModelGroup.model_mappings / ModelMapping.model_groups 关系、
唯一约束、级联删除、disabled 模型可绑定、数据迁移函数。
"""
import os
import pytest
from sqlalchemy import create_engine, text
from sqlalchemy.orm import sessionmaker, Session


import app.models  # noqa: F401, E402
from app.core.database import Base
from app.models.model_group import ModelGroup, ModelGroupStatus, migrate_provider_group_bindings_to_models
from app.models.provider import Provider, ProviderType, ProviderStatus
from app.models.model_mapping import ModelMapping, ModelMappingStatus


TEST_DATABASE_URL = os.environ.get(
    "TEST_DATABASE_URL",
    "mysql+pymysql://token_user:token_password@mysql:3306/token_db_test?charset=utf8mb4",
)

_engine = create_engine(TEST_DATABASE_URL, pool_pre_ping=True)
Base.metadata.create_all(bind=_engine)
TestingSessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=_engine)


def _truncate_all(db: Session):
    """按外键依赖反向截断。"""
    for table in reversed(Base.metadata.sorted_tables):
        db.execute(text(f"SET FOREIGN_KEY_CHECKS=0"))
        db.execute(text(f"TRUNCATE TABLE {table.name}"))
        db.execute(text(f"SET FOREIGN_KEY_CHECKS=1"))
    db.commit()


@pytest.fixture
def db():
    session = TestingSessionLocal()
    _truncate_all(session)
    try:
        yield session
    finally:
        session.close()


@pytest.fixture
def provider(db: Session) -> Provider:
    p = Provider(
        provider_id="prov_a",
        name="Test Provider A",
        type=ProviderType.openai,
        endpoint="https://api.test.com/v1/chat/completions",
        api_key="sk-test",
        status=ProviderStatus.active,
    )
    db.add(p)
    db.commit()
    db.refresh(p)
    return p


@pytest.fixture
def group(db: Session) -> ModelGroup:
    g = ModelGroup(
        group_id="grp_a",
        name="Group A",
        status=ModelGroupStatus.active,
        is_default=1,
    )
    db.add(g)
    db.commit()
    db.refresh(g)
    return g


@pytest.fixture
def models_in_provider(db: Session, provider: Provider):
    m1 = ModelMapping(model_id="model-a", provider_id=provider.provider_id, provider_model="model-a", status=ModelMappingStatus.active)
    m2 = ModelMapping(model_id="model-b", provider_id=provider.provider_id, provider_model="model-b", status=ModelMappingStatus.active)
    db.add_all([m1, m2])
    db.commit()
    return m1, m2


# ---- 关系 / 约束 / 级联 ----

def test_group_model_mappings_relationship_exists(db: Session, group: ModelGroup, models_in_provider):
    """ModelGroup.model_mappings 与 ModelMapping 多对多联通"""
    m1, _ = models_in_provider
    group.model_mappings.append(m1)
    db.commit()

    fresh = db.query(ModelGroup).filter(ModelGroup.group_id == group.group_id).first()
    bound_ids = {m.model_id for m in fresh.model_mappings}
    assert bound_ids == {"model-a"}


def test_model_model_groups_relationship_exists(db: Session, group: ModelGroup, models_in_provider):
    """ModelMapping.model_groups 联通"""
    m1, m2 = models_in_provider
    m1.model_groups.append(group)
    db.commit()

    fresh = db.query(ModelMapping).filter(ModelMapping.model_id == "model-a").first()
    bound_group_ids = {g.group_id for g in fresh.model_groups}
    assert bound_group_ids == {"grp_a"}
    other = db.query(ModelMapping).filter(ModelMapping.model_id == "model-b").first()
    assert other.model_groups == []


def test_pair_can_bind_two_distinct_models(db: Session, group: ModelGroup, models_in_provider):
    """同一分组可绑定多个模型"""
    m1, m2 = models_in_provider
    group.model_mappings = [m1, m2]
    db.commit()

    fresh = db.query(ModelGroup).filter(ModelGroup.group_id == group.group_id).first()
    bound_ids = sorted(m.model_id for m in fresh.model_mappings)
    assert bound_ids == ["model-a", "model-b"]


def test_unique_group_model_constraint(db: Session, group: ModelGroup, models_in_provider):
    """(group_id, model_id) UNIQUE：直接 INSERT 重复行应抛 IntegrityError"""
    m1, _ = models_in_provider
    group.model_mappings.append(m1)
    db.commit()

    with pytest.raises(Exception) as ei:
        db.execute(text(
            "INSERT INTO model_group_model_mappings (group_id, model_id) VALUES (:g, :m)"
        ), {"g": "grp_a", "m": "model-a"})
        db.commit()
    assert "Duplicate" in str(ei.value) or "duplicate" in str(ei.value) or "1062" in str(ei.value)
    db.rollback()


def test_deleting_group_cascades_associations(db: Session, group: ModelGroup, models_in_provider):
    """删除分组时，关联行级联清理（MySQL FK ON DELETE CASCADE）"""
    m1, m2 = models_in_provider
    group.model_mappings = [m1, m2]
    db.commit()

    before = db.execute(text(
        "SELECT COUNT(*) FROM model_group_model_mappings WHERE group_id='grp_a'"
    )).scalar()
    assert before == 2

    db.delete(group)
    db.commit()

    after = db.execute(text(
        "SELECT COUNT(*) FROM model_group_model_mappings WHERE group_id='grp_a'"
    )).scalar()
    assert after == 0


def test_disabled_model_can_be_bound_to_group(db: Session, group: ModelGroup, provider: Provider):
    """规则 §2.9：允许绑定 disabled 模型"""
    m = ModelMapping(
        model_id="model-disabled",
        provider_id=provider.provider_id,
        provider_model="model-disabled",
        status=ModelMappingStatus.disabled,
    )
    db.add(m)
    db.commit()

    group.model_mappings.append(m)
    db.commit()

    fresh = db.query(ModelGroup).filter(ModelGroup.group_id == group.group_id).first()
    bound_ids = {mm.model_id for mm in fresh.model_mappings}
    assert "model-disabled" in bound_ids


# ---- 数据迁移 ----

def test_migrate_expands_single_provider(db: Session, provider: Provider, group: ModelGroup):
    """旧 (provider, group) → 新 (group, model) × 该 provider 下所有 model"""
    m1 = ModelMapping(model_id="model-a", provider_id=provider.provider_id, provider_model="model-a", status=ModelMappingStatus.active)
    m2 = ModelMapping(model_id="model-b", provider_id=provider.provider_id, provider_model="model-b", status=ModelMappingStatus.active)
    db.add_all([m1, m2])
    db.commit()

    db.execute(text(
        "INSERT INTO provider_model_groups (provider_id, group_id) VALUES (:p, :g)"
    ), {"p": provider.provider_id, "g": group.group_id})
    db.commit()

    inserted = migrate_provider_group_bindings_to_models(db)
    assert inserted == 2

    rows = db.execute(text(
        "SELECT model_id FROM model_group_model_mappings WHERE group_id=:g"
    ), {"g": group.group_id}).fetchall()
    assert {r[0] for r in rows} == {"model-a", "model-b"}


def test_migrate_dedupes_when_two_providers_share_a_model_via_group(db: Session, group: ModelGroup):
    """两个 provider 各自有自己的 model，都绑定到同一 group：去重后行数正确"""
    p1 = Provider(provider_id="prov_a", name="A", type=ProviderType.openai,
                  endpoint="https://a/", api_key="k", status=ProviderStatus.active)
    p2 = Provider(provider_id="prov_b", name="B", type=ProviderType.openai,
                  endpoint="https://b/", api_key="k", status=ProviderStatus.active)
    db.add_all([p1, p2])
    db.commit()
    db.add_all([
        ModelMapping(model_id="model-x", provider_id="prov_a", provider_model="x", status=ModelMappingStatus.active),
        ModelMapping(model_id="model-y", provider_id="prov_b", provider_model="y", status=ModelMappingStatus.active),
    ])
    db.commit()

    db.execute(text(
        "INSERT INTO provider_model_groups (provider_id, group_id) VALUES (:p, :g), (:p2, :g)"
    ), {"p": "prov_a", "p2": "prov_b", "g": group.group_id})
    db.commit()

    inserted = migrate_provider_group_bindings_to_models(db)
    assert inserted == 2  # model-x + model-y

    rows = db.execute(text(
        "SELECT model_id FROM model_group_model_mappings WHERE group_id=:g"
    ), {"g": group.group_id}).fetchall()
    assert {r[0] for r in rows} == {"model-x", "model-y"}


def test_migrate_idempotent_when_run_twice(db: Session, provider: Provider, group: ModelGroup):
    """重复执行迁移不应产生重复关联行"""
    db.add(ModelMapping(model_id="model-a", provider_id=provider.provider_id,
                        provider_model="model-a", status=ModelMappingStatus.active))
    db.commit()
    db.execute(text(
        "INSERT INTO provider_model_groups (provider_id, group_id) VALUES (:p, :g)"
    ), {"p": provider.provider_id, "g": group.group_id})
    db.commit()

    migrate_provider_group_bindings_to_models(db)
    second = migrate_provider_group_bindings_to_models(db)
    assert second == 0

    total = db.execute(text(
        "SELECT COUNT(*) FROM model_group_model_mappings WHERE group_id=:g"
    ), {"g": group.group_id}).scalar()
    assert total == 1


def test_migrate_no_rows_returns_zero(db: Session, group: ModelGroup):
    """空数据 → 0，不抛错"""
    assert migrate_provider_group_bindings_to_models(db) == 0
