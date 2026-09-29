"""新模型默认分组绑定与默认组切换语义。"""
import pytest
from sqlalchemy.orm import Session

import app.models  # noqa: F401
from app.models.model import Model, ModelStatus
from app.models.model_group import ModelGroup, ModelGroupStatus, bind_new_model_to_default_group, get_unique_default_group


@pytest.fixture
def default_group(db: Session) -> ModelGroup:
    group = ModelGroup(group_id="grp_default", name="默认", status=ModelGroupStatus.active, is_default=1)
    db.add(group)
    db.commit()
    return group


@pytest.fixture
def another_group(db: Session) -> ModelGroup:
    group = ModelGroup(group_id="grp_other", name="其他", status=ModelGroupStatus.active, is_default=0)
    db.add(group)
    db.commit()
    return group


def test_new_model_binds_to_unique_default(db: Session, default_group):
    model = Model(model_id="new-model")
    db.add(model)
    bind_new_model_to_default_group(db, model)
    db.commit()

    assert {group.group_id for group in model.model_groups} == {"grp_default"}


def test_new_model_unbound_without_unique_default(db: Session):
    db.add_all([
        ModelGroup(group_id="g1", name="一", status=ModelGroupStatus.active, is_default=1),
        ModelGroup(group_id="g2", name="二", status=ModelGroupStatus.active, is_default=1),
    ])
    db.commit()
    model = Model(model_id="new-model")
    db.add(model)
    bind_new_model_to_default_group(db, model)
    db.commit()

    assert model.model_groups == []
    assert get_unique_default_group(db) is None


def test_new_disabled_model_also_binds(db: Session, default_group):
    model = Model(model_id="disabled-model", status=ModelStatus.disabled)
    db.add(model)
    bind_new_model_to_default_group(db, model)
    db.commit()

    assert [group.group_id for group in model.model_groups] == ["grp_default"]


def test_updating_existing_model_preserves_group_binding(db: Session, another_group):
    model = Model(model_id="model", display_name="old")
    model.model_groups.append(another_group)
    db.add(model)
    db.commit()

    model.display_name = "new"
    db.commit()
    db.refresh(model)

    assert {group.group_id for group in model.model_groups} == {"grp_other"}


def test_set_default_clears_other_defaults(db: Session, default_group, another_group):
    from app.services.model_groups_service import set_default_group

    set_default_group(db, "grp_other")
    db.commit()

    assert db.query(ModelGroup).filter_by(group_id="grp_default").one().is_default == 0
    assert db.query(ModelGroup).filter_by(group_id="grp_other").one().is_default == 1


def test_unset_default_does_not_clear_bindings(db: Session, default_group):
    model = Model(model_id="model", model_groups=[default_group])
    db.add(model)
    db.commit()

    from app.services.model_groups_service import unset_default_group
    unset_default_group(db, "grp_default")
    db.commit()

    db.refresh(model)
    assert [group.group_id for group in model.model_groups] == ["grp_default"]
