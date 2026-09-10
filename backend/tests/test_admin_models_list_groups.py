"""
回归测试：模型管理列表的所属分组字段必须反映真实绑定。

Bug：GET /api/v1/admin/models 把 model_groups 硬编码成空列表，导致前端始终显示 -。
"""
import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine, text
from sqlalchemy.orm import sessionmaker
import os

import app.models  # noqa: F401, E402
from app.models.user import User, UserRole, UserStatus
from app.models.model_group import ModelGroup, ModelGroupStatus
from app.models.model import Model as ModelMapping, ModelStatus as ModelMappingStatus
from app.core.security import hash_password_sha256
from app.core.database import Base, get_db

TEST_DATABASE_URL = os.environ.get(
    "TEST_DATABASE_URL",
    "mysql+pymysql://token_user:token_password@mysql:3306/token_db_test?charset=utf8mb4",
)
engine = create_engine(TEST_DATABASE_URL, pool_pre_ping=True)
Base.metadata.create_all(bind=engine)
TestingSessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)


def override_get_db():
    db = TestingSessionLocal()
    try:
        yield db
    finally:
        db.close()


from app.main import app as fastapi_app
fastapi_app.dependency_overrides[get_db] = override_get_db
client = TestClient(fastapi_app)


@pytest.fixture(autouse=True)
def reset_db():
    db = TestingSessionLocal()
    try:
        for table in reversed(Base.metadata.sorted_tables):
            db.execute(text("SET FOREIGN_KEY_CHECKS=0"))
            db.execute(text(f"TRUNCATE TABLE {table.name}"))
            db.execute(text("SET FOREIGN_KEY_CHECKS=1"))
        db.commit()
    finally:
        db.close()
    yield


def _login_admin():
    db = TestingSessionLocal()
    try:
        u = User(
            user_id="usr_admin",
            username="admin",
            email="admin@x",
            password=hash_password_sha256("pwd"),
            role=UserRole.admin,
            status=UserStatus.active,
            model_group_ids="[]",
        )
        db.add(u)
        db.commit()
    finally:
        db.close()
    r = client.post(
        "/api/v1/auth/login",
        data={"username": "admin", "password": hash_password_sha256("pwd")},
    )
    assert r.status_code == 200, r.text
    return r.json()["access_token"]


def _seed_models_with_groups():
    db = TestingSessionLocal()
    try:
        g1 = ModelGroup(group_id="g_one", name="\u5206\u7ec4\u4e00", status=ModelGroupStatus.active, is_default=0)
        g2 = ModelGroup(group_id="g_two", name="\u5206\u7ec4\u4e8c", status=ModelGroupStatus.active, is_default=0)
        db.add_all([g1, g2])
        db.flush()

        m_a = ModelMapping(model_id="m-a", display_name="\u6a21\u578bA",
                           price_per_1k_input=0, price_per_1k_output=0,
                           price_per_request=0, status=ModelMappingStatus.active)
        m_b = ModelMapping(model_id="m-b", display_name="\u6a21\u578bB",
                           price_per_1k_input=0, price_per_1k_output=0,
                           price_per_request=0, status=ModelMappingStatus.active)
        db.add_all([m_a, m_b])
        db.flush()

        # m-a \u7ed1 g1\uff1bm-b \u7ed1 g1 \u548c g2
        m_a.model_groups.append(g1)
        m_b.model_groups.append(g1)
        m_b.model_groups.append(g2)
        db.commit()
    finally:
        db.close()


def test_list_models_returns_bound_group_names():
    """\u6a21\u578b\u5217\u8868\u7684 model_groups \u5b57\u6bb5\u5fc5\u987b\u8fd4\u56de\u771f\u5b9e\u7ed1\u5b9a\u7684\u5206\u7ec4\u540d\u79f0\u3002"""
    tok = _login_admin()
    _seed_models_with_groups()

    r = client.get(
        "/api/v1/admin/models?page=1&page_size=50",
        headers={"Authorization": f"Bearer {tok}"},
    )
    assert r.status_code == 200, r.text
    data = r.json()
    by_id = {item["model_id"]: item for item in data["items"]}

    assert set(by_id["m-a"]["model_groups"]) == {"\u5206\u7ec4\u4e00"}, by_id["m-a"]
    assert set(by_id["m-b"]["model_groups"]) == {"\u5206\u7ec4\u4e00", "\u5206\u7ec4\u4e8c"}, by_id["m-b"]


def test_get_single_model_returns_bound_group_names():
    """\u6a21\u578b\u8be6\u60c5\u7684 model_groups \u5b57\u6bb5\u4e5f\u5fc5\u987b\u8fd4\u56de\u771f\u5b9e\u7ed1\u5b9a\u7684\u5206\u7ec4\u540d\u79f0\u3002"""
    tok = _login_admin()
    _seed_models_with_groups()

    r = client.get(
        "/api/v1/admin/models/m-b",
        headers={"Authorization": f"Bearer {tok}"},
    )
    assert r.status_code == 200, r.text
    data = r.json()
    assert set(data["model_groups"]) == {"\u5206\u7ec4\u4e00", "\u5206\u7ec4\u4e8c"}, data
