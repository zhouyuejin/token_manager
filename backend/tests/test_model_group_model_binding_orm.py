"""当前 ModelGroup 与 Model 关联表约束。"""
import os

import pytest
from sqlalchemy import create_engine, text
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session, sessionmaker

import app.models  # noqa: F401
from app.core.database import Base
from app.models.model import Model, ModelStatus
from app.models.model_group import ModelGroup, ModelGroupStatus


TEST_DATABASE_URL = os.environ.get(
    "TEST_DATABASE_URL",
    "mysql+pymysql://token_user:token_password@mysql:3306/token_db_test?charset=utf8mb4",
)
engine = create_engine(TEST_DATABASE_URL, pool_pre_ping=True)
Base.metadata.create_all(bind=engine)
TestingSessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)


def _truncate_all(db: Session):
    for table in reversed(Base.metadata.sorted_tables):
        db.execute(text("SET FOREIGN_KEY_CHECKS=0"))
        db.execute(text(f"TRUNCATE TABLE {table.name}"))
        db.execute(text("SET FOREIGN_KEY_CHECKS=1"))
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
def group(db: Session) -> ModelGroup:
    group = ModelGroup(group_id="grp_a", name="Group A", status=ModelGroupStatus.active, is_default=1)
    db.add(group)
    db.commit()
    return group


@pytest.fixture
def models(db: Session):
    first, second = Model(model_id="model-a"), Model(model_id="model-b")
    db.add_all([first, second])
    db.commit()
    return first, second


def test_group_models_relationship_is_bidirectional(db: Session, group: ModelGroup, models):
    first, _ = models
    group.models.append(first)
    db.commit()

    fresh = db.query(ModelGroup).filter_by(group_id=group.group_id).one()
    assert {model.model_id for model in fresh.models} == {"model-a"}
    assert [item.group_id for item in db.query(Model).filter_by(model_id="model-a").one().model_groups] == ["grp_a"]


def test_group_can_bind_multiple_models(group: ModelGroup, models):
    group.models = list(models)

    assert sorted(model.model_id for model in group.models) == ["model-a", "model-b"]


def test_unique_group_model_constraint(db: Session, group: ModelGroup, models):
    model, _ = models
    group.models.append(model)
    db.commit()

    with pytest.raises(IntegrityError):
        db.execute(text(
            "INSERT INTO model_group_model_mappings (group_id, model_id) VALUES (:g, :m)"
        ), {"g": "grp_a", "m": "model-a"})
        db.commit()
    db.rollback()


def test_deleting_group_cascades_associations(db: Session, group: ModelGroup, models):
    group.models = list(models)
    db.commit()
    assert db.execute(text(
        "SELECT COUNT(*) FROM model_group_model_mappings WHERE group_id='grp_a'"
    )).scalar() == 2

    db.delete(group)
    db.commit()

    assert db.execute(text(
        "SELECT COUNT(*) FROM model_group_model_mappings WHERE group_id='grp_a'"
    )).scalar() == 0


def test_disabled_model_can_be_bound(db: Session, group: ModelGroup):
    model = Model(model_id="model-disabled", status=ModelStatus.disabled)
    db.add(model)
    group.models.append(model)
    db.commit()

    assert [item.model_id for item in db.query(ModelGroup).filter_by(group_id="grp_a").one().models] == ["model-disabled"]
