"""
测试 API Key 端点与 Model Group 的集成

Task 5: API Key 不再保留独立分组权限，统一由用户分组决定（§2.15）。
Model Group 通过 model_ids 包含模型映射，不再通过 provider_ids。
"""
import json
import pytest
from fastapi.testclient import TestClient
from sqlalchemy.orm import sessionmaker

from app.main import app as fastapi_app
from app.core.database import Base, get_db
from app.models.user import User, UserRole, UserStatus
from app.models.api_key import ApiKey, ApiKeyStatus
from app.models.model_group import ModelGroup, ModelGroupStatus
from app.models.provider import Provider, ProviderType, ProviderStatus
from app.models.model_mapping import ModelMapping, ModelMappingStatus
from app.core.security import hash_password_sha256

# ========== Test Setup ==========
import os
from sqlalchemy import create_engine, text

import app.models  # noqa: F401, E402
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


client = TestClient(fastapi_app)


@pytest.fixture(autouse=True)
def setup_db():
    """每个测试用 TRUNCATE 清理（MySQL）。"""
    _prev_override = fastapi_app.dependency_overrides.get(get_db)

    def _override():
        db = TestingSessionLocal()
        try:
            yield db
        finally:
            db.close()

    fastapi_app.dependency_overrides[get_db] = _override

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

    if _prev_override is not None:
        fastapi_app.dependency_overrides[get_db] = _prev_override
    else:
        fastapi_app.dependency_overrides.pop(get_db, None)


# ========== Helper Functions ==========
def _create_user(db, username="testuser", email="test@example.com", model_group_ids=None):
    """创建普通用户"""
    user = User(
        user_id=f"usr_{username}",
        username=username,
        email=email,
        password=hash_password_sha256("password"),
        role=UserRole.user,
        status=UserStatus.active,
        model_group_ids=model_group_ids or "[]",
    )
    db.add(user)
    return user


def _create_admin(db, username="admin", email="admin@example.com"):
    """创建管理员"""
    admin = User(
        user_id=f"usr_{username}",
        username=username,
        email=email,
        password=hash_password_sha256("adminpass"),
        role=UserRole.admin,
        status=UserStatus.active,
        model_group_ids="[]",
    )
    db.add(admin)
    return admin


def _get_token(username, password):
    """登录获取 token"""
    hashed = hash_password_sha256(password)
    response = client.post(
        "/api/v1/auth/login",
        data={"username": username, "password": hashed},
    )
    assert response.status_code == 200, f"Login failed: {response.json()}"
    return response.json()["access_token"]


def _admin_token():
    """获取管理员 token"""
    return _get_token("admin", "adminpass")


# ========== Tests ==========

class TestAdminModelGroupDefaultEndpoints:
    """测试设置/取消默认分组的端点"""

    def test_set_default_requires_admin(self):
        """非管理员不能设置默认分组"""
        db = TestingSessionLocal()
        try:
            _create_user(db)
            db.commit()
        finally:
            db.close()

        token = _get_token("testuser", "password")
        db = TestingSessionLocal()
        try:
            group = ModelGroup(
                group_id="grp_default",
                name="Default Group",
                status=ModelGroupStatus.active,
            )
            db.add(group)
            db.commit()
        finally:
            db.close()

        response = client.post(
            "/api/v1/admin/model-groups/grp_default/set-default",
            headers={"Authorization": f"Bearer {token}"},
        )
        assert response.status_code == 403

    def test_unset_default_requires_admin(self):
        """非管理员不能取消默认分组"""
        db = TestingSessionLocal()
        try:
            user = _create_user(db)
            db.commit()
        finally:
            db.close()

        db = TestingSessionLocal()
        try:
            group = ModelGroup(
                group_id="grp_default",
                name="Default Group",
                status=ModelGroupStatus.active,
                is_default=1,
            )
            db.add(group)
            db.commit()
        finally:
            db.close()

        token = _get_token("testuser", "password")
        response = client.post(
            "/api/v1/admin/model-groups/grp_default/unset-default",
            headers={"Authorization": f"Bearer {token}"},
        )
        assert response.status_code == 403

    def test_set_default_idempotent(self):
        """重复设置同一分组为默认是幂等的"""
        db = TestingSessionLocal()
        try:
            _create_admin(db)
            db.commit()
        finally:
            db.close()

        db = TestingSessionLocal()
        try:
            group = ModelGroup(
                group_id="grp_idem",
                name="Idempotent Group",
                status=ModelGroupStatus.active,
            )
            db.add(group)
            db.commit()
        finally:
            db.close()

        token = _admin_token()
        response1 = client.post(
            "/api/v1/admin/model-groups/grp_idem/set-default",
            headers={"Authorization": f"Bearer {token}"},
        )
        assert response1.status_code == 200

        response2 = client.post(
            "/api/v1/admin/model-groups/grp_idem/set-default",
            headers={"Authorization": f"Bearer {token}"},
        )
        assert response2.status_code == 200

    def test_unset_default_idempotent(self):
        """重复取消默认分组是幂等的"""
        db = TestingSessionLocal()
        try:
            _create_admin(db)
            db.commit()
        finally:
            db.close()

        db = TestingSessionLocal()
        try:
            group = ModelGroup(
                group_id="grp_unset",
                name="Unset Group",
                status=ModelGroupStatus.active,
                is_default=1,
            )
            db.add(group)
            db.commit()
        finally:
            db.close()

        token = _admin_token()
        response1 = client.post(
            "/api/v1/admin/model-groups/grp_unset/unset-default",
            headers={"Authorization": f"Bearer {token}"},
        )
        assert response1.status_code == 200

        response2 = client.post(
            "/api/v1/admin/model-groups/grp_unset/unset-default",
            headers={"Authorization": f"Bearer {token}"},
        )
        assert response2.status_code == 200

    def test_set_default_clears_previous_default(self):
        """设置新默认分组时，清除旧的默认标记"""
        db = TestingSessionLocal()
        try:
            _create_admin(db)
            db.commit()
        finally:
            db.close()

        db = TestingSessionLocal()
        try:
            old_default = ModelGroup(
                group_id="grp_old",
                name="Old Default",
                status=ModelGroupStatus.active,
                is_default=1,
            )
            new_default = ModelGroup(
                group_id="grp_new",
                name="New Default",
                status=ModelGroupStatus.active,
            )
            db.add(old_default)
            db.add(new_default)
            db.commit()
        finally:
            db.close()

        token = _admin_token()
        response = client.post(
            "/api/v1/admin/model-groups/grp_new/set-default",
            headers={"Authorization": f"Bearer {token}"},
        )
        assert response.status_code == 200

        db = TestingSessionLocal()
        try:
            old = db.query(ModelGroup).filter(ModelGroup.group_id == "grp_old").first()
            new = db.query(ModelGroup).filter(ModelGroup.group_id == "grp_new").first()
            assert old.is_default == 0
            assert new.is_default == 1
        finally:
            db.close()

    def test_set_default_nonexistent_group_returns_404(self):
        """设置不存在的分组为默认返回 404"""
        db = TestingSessionLocal()
        try:
            _create_admin(db)
            db.commit()
        finally:
            db.close()

        token = _admin_token()
        response = client.post(
            "/api/v1/admin/model-groups/nonexistent/set-default",
            headers={"Authorization": f"Bearer {token}"},
        )
        assert response.status_code == 404

    def test_set_default_on_disabled_group_returns_400(self):
        """设置 disabled 分组为默认返回 400"""
        db = TestingSessionLocal()
        try:
            _create_admin(db)
            db.commit()
        finally:
            db.close()

        db = TestingSessionLocal()
        try:
            group = ModelGroup(
                group_id="grp_disabled",
                name="Disabled Group",
                status=ModelGroupStatus.disabled,
            )
            db.add(group)
            db.commit()
        finally:
            db.close()

        token = _admin_token()
        response = client.post(
            "/api/v1/admin/model-groups/grp_disabled/set-default",
            headers={"Authorization": f"Bearer {token}"},
        )
        assert response.status_code == 400


class TestAdminApiKeyEndpoints:
    """测试管理员 API Key 端点"""

    def test_admin_create_key_no_model_groups_param(self):
        """管理员创建 API Key 时不传递 model_group_ids（该参数已移除）"""
        db = TestingSessionLocal()
        try:
            _create_admin(db)
            db.commit()
        finally:
            db.close()

        token = _admin_token()
        response = client.post(
            "/api/v1/api-keys/admin",
            headers={"Authorization": f"Bearer {token}"},
            json={"name": "Admin Key", "user_id": "usr_admin"},
        )
        assert response.status_code == 200
        data = response.json()
        assert "key_id" in data
        # 确保响应中没有 model_group_ids 字段
        assert "model_group_ids" not in data

    def test_admin_list_keys(self):
        """管理员可以列出所有 API Keys"""
        db = TestingSessionLocal()
        try:
            _create_admin(db)
            db.commit()
        finally:
            db.close()

        # 创建 key
        token = _admin_token()
        client.post(
            "/api/v1/api-keys/admin",
            headers={"Authorization": f"Bearer {token}"},
            json={"name": "Admin Key 1", "user_id": "usr_admin"},
        )
        client.post(
            "/api/v1/api-keys/admin",
            headers={"Authorization": f"Bearer {token}"},
            json={"name": "Admin Key 2", "user_id": "usr_admin"},
        )

        response = client.get(
            "/api/v1/api-keys/admin",
            headers={"Authorization": f"Bearer {token}"},
        )
        assert response.status_code == 200
        data = response.json()
        assert "items" in data
        assert len(data["items"]) >= 2
        # 确保列表中的 keys 没有 model_group_ids 字段
        for item in data["items"]:
            assert "model_group_ids" not in item

    def test_admin_update_key(self):
        """管理员可以更新 API Key"""
        db = TestingSessionLocal()
        try:
            _create_admin(db)
            db.commit()
        finally:
            db.close()

        token = _admin_token()
        create_resp = client.post(
            "/api/v1/api-keys/admin",
            headers={"Authorization": f"Bearer {token}"},
            json={"name": "Original Name", "user_id": "usr_admin"},
        )
        key_id = create_resp.json()["key_id"]

        update_resp = client.put(
            f"/api/v1/api-keys/admin/{key_id}",
            headers={"Authorization": f"Bearer {token}"},
            json={"name": "Updated Name"},
        )
        assert update_resp.status_code == 200
        data = update_resp.json()
        assert data["message"] == "更新成功"
        # 验证更新确实生效
        db = TestingSessionLocal()
        try:
            key = db.query(ApiKey).filter(ApiKey.key_id == key_id).first()
            assert key.key_name == "Updated Name"
        finally:
            db.close()


class TestModelGroupCrudWithModelIds:
    """测试 Model Group CRUD 使用 model_ids 而非 provider_ids"""

    def test_create_group_with_model_ids(self):
        """创建分组时指定 model_ids"""
        db = TestingSessionLocal()
        try:
            _create_admin(db)
            # 创建 provider 和 model mapping
            provider = Provider(
                provider_id="prov_test",
                name="Test Provider",
                type=ProviderType.openai,
                endpoint="https://api.test.com/v1",
                api_key="sk-test",
                status=ProviderStatus.active,
                health_status="healthy",
            )
            db.add(provider)
            model_mapping = ModelMapping(
                model_id="gpt-4",
                provider_id="prov_test",
                provider_model="gpt-4",
                status=ModelMappingStatus.active,
            )
            db.add(model_mapping)
            db.commit()
        finally:
            db.close()

        token = _admin_token()
        response = client.post(
            "/api/v1/admin/model-groups",
            headers={"Authorization": f"Bearer {token}"},
            json={
                "name": "Test Group",
                "model_ids": ["gpt-4"],
            },
        )
        assert response.status_code == 200
        data = response.json()
        assert data["name"] == "Test Group"
        assert "gpt-4" in data["model_ids"]
        assert data["group_id"].startswith("mg_")

    def test_update_group_model_ids(self):
        """更新分组的 model_ids"""
        db = TestingSessionLocal()
        try:
            _create_admin(db)
            provider = Provider(
                provider_id="prov_test",
                name="Test Provider",
                type=ProviderType.openai,
                endpoint="https://api.test.com/v1",
                api_key="sk-test",
                status=ProviderStatus.active,
                health_status="healthy",
            )
            db.add(provider)
            model1 = ModelMapping(
                model_id="gpt-4",
                provider_id="prov_test",
                provider_model="gpt-4",
                status=ModelMappingStatus.active,
            )
            model2 = ModelMapping(
                model_id="gpt-3.5",
                provider_id="prov_test",
                provider_model="gpt-3.5-turbo",
                status=ModelMappingStatus.active,
            )
            db.add(model1)
            db.add(model2)
            db.commit()
        finally:
            db.close()

        token = _admin_token()
        # 创建组
        create_resp = client.post(
            "/api/v1/admin/model-groups",
            headers={"Authorization": f"Bearer {token}"},
            json={"name": "Update Group", "model_ids": ["gpt-4"]},
        )
        assert create_resp.status_code == 200
        group_id = create_resp.json()["group_id"]
        # 更新
        response = client.put(
            f"/api/v1/admin/model-groups/{group_id}",
            headers={"Authorization": f"Bearer {token}"},
            json={"model_ids": ["gpt-4", "gpt-3.5"]},
        )
        assert response.status_code == 200
        data = response.json()
        assert "gpt-4" in data["model_ids"]
        assert "gpt-3.5" in data["model_ids"]

    def test_delete_group_with_models_fails(self):
        """删除有关联模型的分组应失败（Plan A）"""
        db = TestingSessionLocal()
        try:
            _create_admin(db)
            provider = Provider(
                provider_id="prov_test",
                name="Test Provider",
                type=ProviderType.openai,
                endpoint="https://api.test.com/v1",
                api_key="sk-test",
                status=ProviderStatus.active,
                health_status="healthy",
            )
            db.add(provider)
            model_mapping = ModelMapping(
                model_id="gpt-4",
                provider_id="prov_test",
                provider_model="gpt-4",
                status=ModelMappingStatus.active,
            )
            db.add(model_mapping)
            db.commit()
        finally:
            db.close()

        token = _admin_token()
        # 创建组并关联模型
        create_resp = client.post(
            "/api/v1/admin/model-groups",
            headers={"Authorization": f"Bearer {token}"},
            json={"name": "Delete Group", "model_ids": ["gpt-4"]},
        )
        assert create_resp.status_code == 200
        group_id = create_resp.json()["group_id"]
        # 尝试删除
        response = client.delete(
            f"/api/v1/admin/model-groups/{group_id}",
            headers={"Authorization": f"Bearer {token}"},
        )
        assert response.status_code == 400
        assert "已绑定" in response.json()["detail"] or "bound" in response.json()["detail"].lower()
