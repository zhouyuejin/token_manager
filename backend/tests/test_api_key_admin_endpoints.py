"""
测试 API Key 创建端点和 Admin Model Group 设置端点

覆盖场景:
- Scenario 1: 默认分组存在，新用户创建 Key → Key 获得默认分组
- Scenario 4: 无默认分组 + 用户无授权 → Key 无分组，访问被拒绝时返回通用错误
- Scenario 6: Admin set-default / unset-default 端点，管理员专有，幂等性
"""
import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool
from sqlalchemy import event

from app.main import app
from app.core.database import Base, get_db
from app.models.user import User, UserRole, UserStatus
from app.models.api_key import ApiKey, ApiKeyStatus
from app.models.model_group import ModelGroup, ModelGroupStatus, api_key_model_groups
from app.models.provider import Provider, ProviderType, ProviderStatus
from app.models.model_mapping import ModelMapping, ModelMappingStatus
from app.core.security import get_password_hash
from app.services.proxy_service import ProxyService

# ========== Test Setup (同 test_proxy_service_model_group.py 的模式) ==========
import sqlalchemy
from sqlalchemy import Integer, TypeDecorator


class _BigIntegerCompat(TypeDecorator):
    """SQLite -> Integer（自增），MySQL -> BigInteger。"""
    impl = Integer
    cache_ok = True

    def load_dialect_impl(self, dialect):
        if dialect.name in ("mysql", "mariadb"):
            return dialect.type_descriptor(sqlalchemy.BigInteger())
        return dialect.type_descriptor(Integer())


sqlalchemy.BigInteger = _BigIntegerCompat

TEST_DATABASE_URL = "sqlite:///:memory:"
engine = create_engine(
    TEST_DATABASE_URL,
    connect_args={"check_same_thread": False},
    poolclass=StaticPool,
)
TestingSessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)


def override_get_db():
    db = TestingSessionLocal()
    try:
        yield db
    finally:
        db.close()


app.dependency_overrides[get_db] = override_get_db
client = TestClient(app)


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


@pytest.fixture(autouse=True)
def setup_db():
    Base.metadata.create_all(bind=engine)
    _id_counters.clear()
    yield
    for table in reversed(Base.metadata.sorted_tables):
        TestingSessionLocal().execute(table.delete())
    _id_counters.clear()


# ========== Helper Functions ==========
def _create_user(db, username="testuser", email="test@example.com", model_group_ids=None):
    """创建普通用户"""
    user = User(
        user_id=f"usr_{username}",
        username=username,
        email=email,
        password=get_password_hash("password"),
        role=UserRole.user,
        status=UserStatus.active,
        model_group_ids=model_group_ids,
    )
    db.add(user)
    db.commit()
    db.refresh(user)
    return user


def _create_admin(db, username="admin", email="admin@example.com"):
    """创建管理员用户"""
    admin = User(
        user_id=f"usr_{username}",
        username=username,
        email=email,
        password=get_password_hash("adminpass"),
        role=UserRole.admin,
        status=UserStatus.active,
    )
    db.add(admin)
    db.commit()
    db.refresh(admin)
    return admin


def _get_token(username, password):
    """获取用户token"""
    response = client.post(
        "/api/v1/auth/login",
        data={"username": username, "password": password},
    )
    if response.status_code == 200:
        return response.json().get("access_token")
    return None


# ========== Scenario 1: 默认分组存在，新用户创建 Key → Key 获得默认分组 ==========
class TestApiKeyCreateWithDefaultGroup:
    """Scenario 1: Default group set, new user creates key → key gets default group"""

    def test_create_key_gets_default_group(self):
        """用户创建 API Key 时，如果没有指定 model_group_ids，应自动获得默认分组"""
        db = TestingSessionLocal()
        try:
            # 1. 创建默认分组
            default_group = ModelGroup(
                group_id="grp_default",
                name="默认分组",
                status=ModelGroupStatus.active,
                is_default=1,
            )
            db.add(default_group)
            
            # 2. 关联供应商以便后续测试
            provider = Provider(
                provider_id="prov_test",
                name="Test Provider",
                type=ProviderType.openai,
                endpoint="https://api.test.com/v1/chat/completions",
                api_key="sk-test",
                status=ProviderStatus.active,
            )
            provider.model_groups.append(default_group)
            db.add(provider)
            
            # 3. 创建模型映射
            model_mapping = ModelMapping(
                model_id="gpt-4",
                provider_id="prov_test",
                provider_model="gpt-4",
                status=ModelMappingStatus.active,
            )
            db.add(model_mapping)
            
            # 4. 创建普通用户（无 model_group_ids）
            user = _create_user(db, "newuser", "newuser@example.com", model_group_ids=None)
            
            db.commit()
        finally:
            db.close()

        # 5. 用户登录获取 token
        token = _get_token("newuser", "password")
        assert token is not None, "Failed to get user token"

        # 6. 用户创建 API Key
        response = client.post(
            "/api/v1/api-keys",
            headers={"Authorization": f"Bearer {token}"},
            json={"name": "My Test Key"},
        )
        assert response.status_code == 200, f"Failed to create key: {response.json()}"
        
        key_data = response.json()
        key_id = key_data["key_id"]
        
        # 7. 验证 Key 在数据库中有关联的默认分组
        db = TestingSessionLocal()
        try:
            api_key = db.query(ApiKey).filter(ApiKey.key_id == key_id).first()
            assert api_key is not None
            
            # 获取关联的分组
            key_groups = api_key.model_groups
            group_ids = [g.group_id for g in key_groups]
            
            # 验证：包含默认分组
            assert "grp_default" in group_ids, f"Expected grp_default in {group_ids}"
            
            # 验证：只有默认分组（用户没有额外的 model_group_ids）
            assert len(group_ids) == 1, f"Expected only default group, got {group_ids}"
        finally:
            db.close()

    def test_create_key_with_user_extra_groups_includes_both(self):
        """用户有额外授权分组 + 默认分组存在 → Key 获得两者的并集"""
        db = TestingSessionLocal()
        try:
            # 1. 创建默认分组
            default_group = ModelGroup(
                group_id="grp_default",
                name="默认分组",
                status=ModelGroupStatus.active,
                is_default=1,
            )
            db.add(default_group)
            
            # 2. 创建额外分组
            extra_group = ModelGroup(
                group_id="grp_extra",
                name="额外分组",
                status=ModelGroupStatus.active,
                is_default=0,
            )
            db.add(extra_group)
            
            # 3. 创建供应商
            provider = Provider(
                provider_id="prov_test",
                name="Test Provider",
                type=ProviderType.openai,
                endpoint="https://api.test.com/v1/chat/completions",
                api_key="sk-test",
                status=ProviderStatus.active,
            )
            provider.model_groups.append(default_group)
            provider.model_groups.append(extra_group)
            db.add(provider)
            
            # 4. 创建模型映射
            model_mapping = ModelMapping(
                model_id="gpt-4",
                provider_id="prov_test",
                provider_model="gpt-4",
                status=ModelMappingStatus.active,
            )
            db.add(model_mapping)
            
            # 5. 创建有额外授权的普通用户
            user = _create_user(
                db, "extruser", "extruser@example.com", 
                model_group_ids='["grp_extra"]'
            )
            
            db.commit()
        finally:
            db.close()

        # 6. 用户登录获取 token
        token = _get_token("extruser", "password")
        assert token is not None, "Failed to get user token"

        # 7. 用户创建 API Key
        response = client.post(
            "/api/v1/api-keys",
            headers={"Authorization": f"Bearer {token}"},
            json={"name": "Key With Extra Groups"},
        )
        assert response.status_code == 200, f"Failed to create key: {response.json()}"
        
        key_id = response.json()["key_id"]
        
        # 8. 验证 Key 同时拥有默认分组和额外分组
        db = TestingSessionLocal()
        try:
            api_key = db.query(ApiKey).filter(ApiKey.key_id == key_id).first()
            key_groups = api_key.model_groups
            group_ids = [g.group_id for g in key_groups]
            
            # 验证：两者都有
            assert "grp_default" in group_ids, f"Expected grp_default in {group_ids}"
            assert "grp_extra" in group_ids, f"Expected grp_extra in {group_ids}"
            assert len(group_ids) == 2, f"Expected both groups, got {group_ids}"
        finally:
            db.close()


# ========== Scenario 4: 无默认分组 + 用户无授权 → Key 无分组，访问被拒绝时返回通用错误 ==========
class TestApiKeyCreateWithoutDefaultGroup:
    """Scenario 4: No default group + no user auth → key has no groups, error is generic"""

    def test_create_key_no_default_no_user_groups(self):
        """无默认分组且用户无额外授权 → Key 无分组"""
        db = TestingSessionLocal()
        try:
            # 1. 创建非默认分组（不设置 is_default=1）
            extra_group = ModelGroup(
                group_id="grp_extra",
                name="额外分组",
                status=ModelGroupStatus.active,
                is_default=0,
            )
            db.add(extra_group)
            
            # 2. 创建供应商和模型映射
            provider = Provider(
                provider_id="prov_test",
                name="Test Provider",
                type=ProviderType.openai,
                endpoint="https://api.test.com/v1/chat/completions",
                api_key="sk-test",
                status=ProviderStatus.active,
            )
            provider.model_groups.append(extra_group)
            db.add(provider)
            
            model_mapping = ModelMapping(
                model_id="gpt-4",
                provider_id="prov_test",
                provider_model="gpt-4",
                status=ModelMappingStatus.active,
            )
            db.add(model_mapping)
            
            # 3. 创建无 model_group_ids 的普通用户
            user = _create_user(db, "nogroups", "nogroups@example.com", model_group_ids=None)
            
            db.commit()
        finally:
            db.close()

        # 4. 用户登录
        token = _get_token("nogroups", "password")
        assert token is not None

        # 5. 创建 API Key
        response = client.post(
            "/api/v1/api-keys",
            headers={"Authorization": f"Bearer {token}"},
            json={"name": "No Groups Key"},
        )
        assert response.status_code == 200
        
        key_id = response.json()["key_id"]
        
        # 6. 验证 Key 无分组
        db = TestingSessionLocal()
        try:
            api_key = db.query(ApiKey).filter(ApiKey.key_id == key_id).first()
            key_groups = api_key.model_groups
            assert len(key_groups) == 0, f"Expected no groups, got {[g.group_id for g in key_groups]}"
        finally:
            db.close()

    def test_access_denied_generic_error(self):
        """用户无分组时访问模型 → 返回通用错误，不泄露分组信息"""
        db = TestingSessionLocal()
        try:
            # 1. 创建非默认分组
            extra_group = ModelGroup(
                group_id="grp_extra",
                name="额外分组",
                status=ModelGroupStatus.active,
                is_default=0,
            )
            db.add(extra_group)
            
            # 2. 创建供应商和模型映射
            provider = Provider(
                provider_id="prov_test",
                name="Test Provider",
                type=ProviderType.openai,
                endpoint="https://api.test.com/v1/chat/completions",
                api_key="sk-test",
                status=ProviderStatus.active,
            )
            provider.model_groups.append(extra_group)
            db.add(provider)
            
            model_mapping = ModelMapping(
                model_id="gpt-4",
                provider_id="prov_test",
                provider_model="gpt-4",
                status=ModelMappingStatus.active,
            )
            db.add(model_mapping)
            
            # 3. 创建用户（无分组）
            user = _create_user(db, "denieduser", "denieduser@example.com", model_group_ids=None)
            
            # 4. 创建用户的 API Key
            api_key = ApiKey(
                key_id="key_denied",
                user_id=user.user_id,
                api_key="tmk_denied_key",
                key_name="Denied Key",
                status=ApiKeyStatus.active,
            )
            db.add(api_key)
            
            db.commit()
        finally:
            db.close()

        # 5. 测试 ProxyService.check_model_group_access
        db = TestingSessionLocal()
        try:
            user = db.query(User).filter(User.user_id == "usr_denieduser").first()
            api_key = db.query(ApiKey).filter(ApiKey.key_id == "key_denied").first()
            
            service = ProxyService(db)
            result = service.check_model_group_access(api_key, user, "gpt-4")
            
            # 验证：拒绝访问
            assert result["allowed"] is False
            
            # 验证：通用错误信息
            assert result["message"] == "当前 Key 未被授权访问该模型"
            
            # 验证：不泄露分组信息
            msg = result["message"].lower()
            assert "default" not in msg
            assert "分组" not in result["message"]
            assert "group" not in msg
        finally:
            db.close()


# ========== Scenario 6: Admin set-default / unset-default 端点 ==========
class TestAdminModelGroupDefaultEndpoints:
    """Scenario 6: Admin set-default / unset-default endpoints - admin only, idempotent"""

    def test_set_default_requires_admin(self):
        """set-default 端点仅管理员可用"""
        db = TestingSessionLocal()
        try:
            # 创建普通用户
            user = _create_user(db, "regular", "regular@example.com", model_group_ids=None)
            db.commit()
        finally:
            db.close()

        token = _get_token("regular", "password")
        assert token is not None

        # 普通用户尝试设置默认分组 → 403
        response = client.post(
            "/api/v1/admin/model-groups/grp_test/set-default",
            headers={"Authorization": f"Bearer {token}"},
        )
        assert response.status_code == 403

    def test_unset_default_requires_admin(self):
        """unset-default 端点仅管理员可用"""
        db = TestingSessionLocal()
        try:
            user = _create_user(db, "regular2", "regular2@example.com", model_group_ids=None)
            db.commit()
        finally:
            db.close()

        token = _get_token("regular2", "password")
        assert token is not None

        # 普通用户尝试取消默认分组 → 403
        response = client.post(
            "/api/v1/admin/model-groups/grp_test/unset-default",
            headers={"Authorization": f"Bearer {token}"},
        )
        assert response.status_code == 403

    def test_set_default_idempotent(self):
        """set-default 端点幂等：重复调用结果相同"""
        db = TestingSessionLocal()
        try:
            # 1. 创建管理员
            admin = _create_admin(db, "testadmin", "testadmin@example.com")
            
            # 2. 创建分组
            group = ModelGroup(
                group_id="grp_test",
                name="测试分组",
                status=ModelGroupStatus.active,
                is_default=0,
            )
            db.add(group)
            db.commit()
        finally:
            db.close()

        token = _get_token("testadmin", "adminpass")
        assert token is not None

        # 第一次设置默认
        response1 = client.post(
            "/api/v1/admin/model-groups/grp_test/set-default",
            headers={"Authorization": f"Bearer {token}"},
        )
        assert response1.status_code == 200

        # 第二次设置默认（幂等）
        response2 = client.post(
            "/api/v1/admin/model-groups/grp_test/set-default",
            headers={"Authorization": f"Bearer {token}"},
        )
        assert response2.status_code == 200

        # 验证分组确实是默认
        db = TestingSessionLocal()
        try:
            group = db.query(ModelGroup).filter(ModelGroup.group_id == "grp_test").first()
            assert group.is_default == 1
        finally:
            db.close()

    def test_unset_default_idempotent(self):
        """unset-default 端点幂等：重复调用结果相同"""
        db = TestingSessionLocal()
        try:
            admin = _create_admin(db, "testadmin2", "testadmin2@example.com")
            
            group = ModelGroup(
                group_id="grp_test2",
                name="测试分组2",
                status=ModelGroupStatus.active,
                is_default=1,
            )
            db.add(group)
            db.commit()
        finally:
            db.close()

        token = _get_token("testadmin2", "adminpass")
        assert token is not None

        # 第一次取消默认
        response1 = client.post(
            "/api/v1/admin/model-groups/grp_test2/unset-default",
            headers={"Authorization": f"Bearer {token}"},
        )
        assert response1.status_code == 200

        # 第二次取消默认（幂等）
        response2 = client.post(
            "/api/v1/admin/model-groups/grp_test2/unset-default",
            headers={"Authorization": f"Bearer {token}"},
        )
        assert response2.status_code == 200

        # 验证分组已取消默认
        db = TestingSessionLocal()
        try:
            group = db.query(ModelGroup).filter(ModelGroup.group_id == "grp_test2").first()
            assert group.is_default == 0
        finally:
            db.close()

    def test_multiple_default_groups_allowed(self):
        """GC-6: 允许多个默认分组"""
        db = TestingSessionLocal()
        try:
            admin = _create_admin(db, "testadmin3", "testadmin3@example.com")
            
            group1 = ModelGroup(
                group_id="grp_d1",
                name="默认分组1",
                status=ModelGroupStatus.active,
                is_default=0,
            )
            group2 = ModelGroup(
                group_id="grp_d2",
                name="默认分组2",
                status=ModelGroupStatus.active,
                is_default=0,
            )
            db.add_all([group1, group2])
            db.commit()
        finally:
            db.close()

        token = _get_token("testadmin3", "adminpass")
        assert token is not None

        # 设置两个分组为默认
        client.post(
            "/api/v1/admin/model-groups/grp_d1/set-default",
            headers={"Authorization": f"Bearer {token}"},
        )
        client.post(
            "/api/v1/admin/model-groups/grp_d2/set-default",
            headers={"Authorization": f"Bearer {token}"},
        )

        # 验证两个都是默认
        db = TestingSessionLocal()
        try:
            group1 = db.query(ModelGroup).filter(ModelGroup.group_id == "grp_d1").first()
            group2 = db.query(ModelGroup).filter(ModelGroup.group_id == "grp_d2").first()
            assert group1.is_default == 1
            assert group2.is_default == 1
        finally:
            db.close()

    def test_set_default_nonexistent_group_returns_404(self):
        """设置不存在的分组为默认 → 404"""
        db = TestingSessionLocal()
        try:
            admin = _create_admin(db, "testadmin4", "testadmin4@example.com")
            db.commit()
        finally:
            db.close()

        token = _get_token("testadmin4", "adminpass")
        assert token is not None

        response = client.post(
            "/api/v1/admin/model-groups/nonexistent/set-default",
            headers={"Authorization": f"Bearer {token}"},
        )
        assert response.status_code == 404
