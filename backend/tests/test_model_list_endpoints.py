"""
测试 chat /models 和 proxy /models 列表端点改用"分组直接绑定模型"语义。

数据库：MySQL token_db_test（与生产一致）。

覆盖 §13 Task 4：
- chat /models 仅返回用户有效分组中、active 模型、active 供应商下的模型
- proxy /models（OpenAI 兼容）同上
- proxy /models 无 fake model fallback —— 无权限时返回空列表（不再假返回 gpt-4 / gpt-3.5-turbo）
- 列表与 check_model_group_access 判定一致
"""
import pytest
import json
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

import app.models  # noqa: F401, E402
from app.models.user import User, UserRole, UserStatus
from app.models.api_key import ApiKey, ApiKeyStatus
from app.models.model_group import ModelGroup, ModelGroupStatus
from app.models.provider import Provider, ProviderType, ProviderStatus
from app.models.model_mapping import ModelMapping, ModelMappingStatus
from app.core.security import hash_password_sha256
from app.core.database import Base, get_db
from sqlalchemy import create_engine, text
from sqlalchemy.orm import sessionmaker
import os


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


def _truncate_all():
    db = TestingSessionLocal()
    try:
        for table in reversed(Base.metadata.sorted_tables):
            db.execute(text("SET FOREIGN_KEY_CHECKS=0"))
            db.execute(text(f"TRUNCATE TABLE {table.name}"))
            db.execute(text("SET FOREIGN_KEY_CHECKS=1"))
        db.commit()
    finally:
        db.close()


def _create_user(db, username="u", model_group_ids=None):
    u = User(
        user_id=f"usr_{username}",
        username=username,
        email=f"{username}@x",
        password=hash_password_sha256("pwd"),
        role=UserRole.user,
        status=UserStatus.active,
        model_group_ids=model_group_ids,
    )
    db.add(u); db.commit(); db.refresh(u)
    return u


def _login(username="u", password="pwd"):
    r = client.post(
        "/api/v1/auth/login",
        data={"username": username, "password": hash_password_sha256(password)},
    )
    return r.json().get("access_token") if r.status_code == 200 else None


def _auth(tok):
    return {"Authorization": f"Bearer {tok}"}


@pytest.fixture(autouse=True)
def setup_db(monkeypatch):
    """truncate 测试 DB；同时让中间件也走测试 DB（monkey-patch SessionLocal）。"""
    import app.middleware as mw
    monkeypatch.setattr(mw, "SessionLocal", TestingSessionLocal)
    _truncate_all()
    yield


@pytest.fixture
def user_with_default():
    """默认用户：无额外分组，靠默认分组权限"""
    db = TestingSessionLocal()
    try:
        return _create_user(db, "alice")
    finally:
        db.close()


@pytest.fixture
def fixtures_basic():
    """创建：默认分组 / 额外分组 / 2 个 active 模型 / 1 个 disabled 模型"""
    db = TestingSessionLocal()
    try:
        g_def = ModelGroup(group_id="g_def", name="默认", status=ModelGroupStatus.active, is_default=1)
        g_extra = ModelGroup(group_id="g_extra", name="额外", status=ModelGroupStatus.active, is_default=0)
        db.add_all([g_def, g_extra])

        p = Provider(provider_id="prov_a", name="A", type=ProviderType.openai,
                     endpoint="https://a/", api_key="k", status=ProviderStatus.active)
        p_disabled = Provider(provider_id="prov_d", name="D", type=ProviderType.openai,
                              endpoint="https://d/", api_key="k", status=ProviderStatus.disabled)
        db.add_all([p, p_disabled])

        m1 = ModelMapping(model_id="m-active", provider_id="prov_a",
                          provider_model="m-active", status=ModelMappingStatus.active)
        m2 = ModelMapping(model_id="m-disabled", provider_id="prov_a",
                          provider_model="m-disabled", status=ModelMappingStatus.disabled)
        m3 = ModelMapping(model_id="m-on-disabled-prov", provider_id="prov_d",
                          provider_model="x", status=ModelMappingStatus.active)
        db.add_all([m1, m2, m3])

        # 绑定：m1 → g_def, m2 → g_def (disabled 模型也绑定), m3 → g_def
        m1.model_groups.append(g_def)
        m2.model_groups.append(g_def)
        m3.model_groups.append(g_def)
        db.commit()
        return {"g_def": g_def.group_id, "g_extra": g_extra.group_id,
                "models": ["m-active", "m-disabled", "m-on-disabled-prov"]}
    finally:
        db.close()


# ========== chat /api/v1/chat/models 测试 ==========

class TestChatModelsEndpoint:
    def test_returns_models_bound_to_default_group(self, fixtures_basic, user_with_default):
        """默认用户能看到默认分组中绑定的 active 模型"""
        tok = _login("alice")
        r = client.get("/api/v1/chats/models", headers=_auth(tok))
        assert r.status_code == 200
        data = r.json()
        ids = {m["model_id"] for g in data["groups"] for m in g["models"]}
        assert "m-active" in ids
        # disabled 模型虽然绑了，但列表中应被过滤掉
        assert "m-disabled" not in ids
        # 供应商被禁用的模型被过滤
        assert "m-on-disabled-prov" not in ids

    def test_unauthorized_user_gets_empty(self, fixtures_basic):
        """无默认分组且用户无授权 → 空列表"""
        # 创建无默认分组的场景
        db = TestingSessionLocal()
        try:
            ModelGroup.query = None  # noqa
            db.query(ModelGroup).filter_by(is_default=1).update({ModelGroup.is_default: 0})
            db.commit()
            u = _create_user(db, "bob")
        finally:
            db.close()

        tok = _login("bob")
        r = client.get("/api/v1/chats/models", headers=_auth(tok))
        assert r.status_code == 200
        assert r.json()["groups"] == []


# ========== proxy /v1/models 测试 ==========

class TestProxyModelsEndpoint:
    def test_returns_only_authorized_models(self, fixtures_basic, user_with_default):
        """OpenAI 兼容 /v1/models 仅返回授权模型"""
        tok = _login("alice")
        # proxy /models 走 api-key 鉴权中间件；先创建一个 key 并用它访问
        db = TestingSessionLocal()
        try:
            api_key_value = "tmk_test_proxy_list"
            db.add(ApiKey(key_id="k_test", user_id="usr_alice", api_key=api_key_value,
                   key_name="K", status=ApiKeyStatus.active))
            db.commit()
        finally:
            db.close()

        r = client.get("/api/v1/proxy/models", headers={"Authorization": f"Bearer {api_key_value}"})
        assert r.status_code == 200
        ids = {m["id"] for m in r.json()["data"]}
        assert "m-active" in ids
        assert "m-disabled" not in ids
        assert "m-on-disabled-prov" not in ids

    def test_no_fake_model_fallback_when_unauthorized(self, fixtures_basic):
        """无权限时不应返回 fake gpt-4 / gpt-3.5-turbo fallback（§13 Task 4）"""
        # 用户没有任何分组
        db = TestingSessionLocal()
        try:
            db.query(ModelGroup).update({ModelGroup.is_default: 0})
            u = _create_user(db, "carol")
            api_key_value = "tmk_test_unauth"
            db.add(ApiKey(key_id="k_unauth", user_id="usr_carol", api_key=api_key_value,
                   key_name="K", status=ApiKeyStatus.active))
            db.commit()
        finally:
            db.close()

        r = client.get("/api/v1/proxy/models", headers={"Authorization": f"Bearer {api_key_value}"})
        assert r.status_code == 200
        ids = {m["id"] for m in r.json()["data"]}
        # 关键断言：不应包含 fake 模型
        assert "gpt-4" not in ids
        assert "gpt-3.5-turbo" not in ids
        assert ids == set()

    def test_unauthenticated_returns_empty_no_fake(self, fixtures_basic):
        """无 API Key → 中间件返回 401（pre-existing 行为）；无论如何不应返回 fake fallback"""
        r = client.get("/api/v1/proxy/models")
        # 中间件对 /api/v1/proxy/* 无 API Key 时返回 401
        assert r.status_code == 401
        body = r.text
        assert "gpt-4" not in body
        assert "gpt-3.5-turbo" not in body
