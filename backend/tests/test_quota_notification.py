"""新用户注册额度控制与管理员通知 — 端到端测试"""
import os
import pytest
import secrets
from unittest.mock import patch, MagicMock

from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.main import app
from app.core.database import Base, get_db
from app.models.user import User, UserRole, UserStatus
from app.models.api_key import ApiKey
from app.models.provider import Provider
from app.models.model_mapping import ModelMapping, ModelMappingStatus
from app.core.security import hash_password_sha256

TEST_DATABASE_URL = os.environ.get(
    "TEST_DATABASE_URL",
    "mysql+pymysql://token_user:token_password@mysql:3306/token_db_test?charset=utf8mb4",
)
engine = create_engine(TEST_DATABASE_URL, pool_pre_ping=True)
TestingSessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)


def override_get_db():
    db = TestingSessionLocal()
    try:
        yield db
    finally:
        db.close()


app.dependency_overrides[get_db] = override_get_db
client = TestClient(app)


@pytest.fixture(autouse=True)
def setup_db():
    Base.metadata.create_all(bind=engine)
    yield
    db = TestingSessionLocal()
    try:
        for table in reversed(Base.metadata.sorted_tables):
            db.execute(__import__("sqlalchemy").text("SET FOREIGN_KEY_CHECKS=0"))
            db.execute(__import__("sqlalchemy").text(f"TRUNCATE TABLE {table.name}"))
            db.execute(__import__("sqlalchemy").text("SET FOREIGN_KEY_CHECKS=1"))
        db.commit()
    finally:
        db.close()


def _create_admin(db, username="admin", email="admin@test.com"):
    admin = User(
        user_id=f"usr_{username}_{secrets.token_hex(4)}",
        username=username,
        email=email,
        password=hash_password_sha256("adminpass"),
        role=UserRole.admin,
        status=UserStatus.active,
        quota=0,
    )
    db.add(admin)
    db.commit()
    return admin


def _create_user(db, username, email, quota=0):
    user = User(
        user_id=f"usr_{username}_{secrets.token_hex(4)}",
        username=username,
        email=email,
        password=hash_password_sha256("userpass"),
        role=UserRole.user,
        status=UserStatus.active,
        quota=quota,
        quota_used=0,
    )
    db.add(user)
    db.commit()
    db.refresh(user)
    return user


def _create_provider_and_model(db, user):
    """创建最少配置的 provider + model_mapping + api_key"""
    provider = Provider(
        provider_id=f"prov_{secrets.token_hex(4)}",
        name="TestProvider",
        type="openai",
        endpoint="https://api.test.com",
        api_key="sk-test",
        priority=50,
        status="active",
    )
    db.add(provider)
    db.commit()

    model = ModelMapping(
        model_id="test-model-001",
        display_name="TestModel",
        provider_id=provider.provider_id,
        provider_model="gpt-3.5-turbo",
        status=ModelMappingStatus.active,
    )
    db.add(model)
    db.commit()

    api_key = ApiKey(
        key_id=f"key_{secrets.token_hex(8)}",
        user_id=user.user_id,
        key_name="test-key",
        api_key=hash_password_sha256("test_secret_key"),
        status="active",
    )
    db.add(api_key)
    db.commit()
    return provider, model, api_key


# =============================================================================
# Test 1: 注册新用户默认额度
# =============================================================================
class TestRegisterDefaultQuota:
    def test_new_user_has_default_quota(self):
        """新注册用户 quota == DEFAULT_NEW_USER_QUOTA（0）"""
        unique = secrets.token_hex(4)
        resp = client.post("/api/v1/auth/register", json={
            "username": f"newuser_{unique}",
            "email": f"new_{unique}@test.com",
            "password": hash_password_sha256("userpass"),
        })
        assert resp.status_code == 200
        data = resp.json()
        assert data["username"] == f"newuser_{unique}"

        # 从数据库确认 quota
        db = TestingSessionLocal()
        try:
            user = db.query(User).filter(User.user_id == data["user_id"]).first()
            assert user is not None
            from app.core.config import settings
            assert user.quota == settings.DEFAULT_NEW_USER_QUOTA
        finally:
            db.close()


# =============================================================================
# Test 2: 新用户注册后管理员收到通知
# =============================================================================
class TestRegisterNotifiesAdmin:
    def test_admin_receives_user_registered_notification(self):
        """注册新用户后，管理员收到 type=user_registered 的通知"""
        db = TestingSessionLocal()
        try:
            # 先创建一个管理员
            admin = _create_admin(db, username="notif_admin", email="notif_admin@test.com")
            admin_user_id = admin.user_id

            # 清空通知表
            db.execute(__import__("sqlalchemy").text("TRUNCATE TABLE notifications"))
            db.commit()

            # 注册新用户
            unique = secrets.token_hex(4)
            resp = client.post("/api/v1/auth/register", json={
                "username": f"notif_user_{unique}",
                "email": f"notif_{unique}@test.com",
                "password": hash_password_sha256("userpass"),
            })
            assert resp.status_code == 200
            new_username = f"notif_user_{unique}"
            new_email = f"notif_{unique}@test.com"
        finally:
            db.close()

        # 验证通知
        db2 = TestingSessionLocal()
        try:
            from app.models.notification import Notification, NotificationType
            notifs = db2.query(Notification).filter(
                Notification.user_id == admin_user_id
            ).all()
            assert len(notifs) >= 1, "管理员应收到至少一条通知"
            notif = notifs[0]
            assert notif.type == NotificationType.user_registered
            assert notif.title == "新用户注册"
            assert new_username in notif.content
            assert new_email in notif.content
            import json
            meta = json.loads(notif.extra_data) if notif.extra_data else {}
            assert "user_id" in meta or "username" in meta
        finally:
            db2.close()


# =============================================================================
# Test 3: 无管理员时注册不报错
# =============================================================================
class TestRegisterNoAdmin:
    def test_register_succeeds_without_any_admin(self):
        """没有任何管理员时，注册仍然成功"""
        unique = secrets.token_hex(4)
        resp = client.post("/api/v1/auth/register", json={
            "username": f"solo_{unique}",
            "email": f"solo_{unique}@test.com",
            "password": hash_password_sha256("userpass"),
        })
        # 应该成功，不应因无管理员而报错
        assert resp.status_code == 200


# =============================================================================
# Test 4-7: check_quota 四种报错
# =============================================================================
class TestCheckQuotaErrors:
    @patch("app.services.proxy_service.ProxyService.forward_stream_request")
    def test_quota_zero_returns_403(self, mock_forward,):
        """quota=0 时返回 403，reason=quota_zero"""
        mock_forward.return_value = iter([])
        db = TestingSessionLocal()
        try:
            user = _create_user(db, "qzero", "qzero@test.com", quota=0)
            _, _, api_key = _create_provider_and_model(db, user)
            api_key_str = api_key.api_key
        finally:
            db.close()

        resp = client.post(
            "/api/v1/chat/completions",
            json={"model": "test-model-001", "messages": [{"role": "user", "content": "hi"}]},
            headers={"X-API-Key": api_key_str},
        )
        assert resp.status_code == 403
        assert "额度为 0" in resp.json()["detail"]

    @patch("app.services.proxy_service.ProxyService.forward_stream_request")
    def test_quota_insufficient_returns_403(self, mock_forward):
        """quota 有值但剩余不足时返回 403，reason=quota_insufficient"""
        mock_forward.return_value = iter([])
        db = TestingSessionLocal()
        try:
            user = _create_user(db, "qinsuff", "qinsuff@test.com", quota=100)
            user.quota_used = 99
            db.commit()
            _, _, api_key = _create_provider_and_model(db, user)
            api_key_str = api_key.api_key
        finally:
            db.close()

        resp = client.post(
            "/api/v1/chat/completions",
            json={"model": "test-model-001", "messages": [{"role": "user", "content": "hi"}]},
            headers={"X-API-Key": api_key_str},
        )
        assert resp.status_code == 403
        detail = resp.json()["detail"]
        assert "额度不足" in detail

# =============================================================================
# Test 5: 管理员调整额度通知
# =============================================================================
class TestQuotaAdjustNotifications:
    def _get_token(self, username, password):
        """登录并返回 access_token"""
        response = client.post(
            "/api/v1/auth/login",
            data={"username": username, "password": hash_password_sha256(password)},
        )
        assert response.status_code == 200, f"Login failed: {response.json()}"
        return response.json()["access_token"]

    def _admin_token(self):
        return self._get_token("admin", "adminpass")

    def test_quota_increase_creates_notification(self):
        """管理员增加额度，DB 中存在 quota_increase 通知，内容含增加额度"""
        db = TestingSessionLocal()
        try:
            admin = _create_admin(db)
            user = _create_user(db, "inc_user", "inc@test.com", quota=100)
            db.commit()
            user_id = user.user_id
        finally:
            db.close()

        token = self._admin_token()
        resp = client.post(
            f"/api/v1/admin/users/{user_id}/quota",
            json={"amount": 50, "reason": "bonus"},
            headers={"Authorization": f"Bearer {token}"},
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["new_quota"] == 150

        # 验证 DB 中有 quota_increase 通知
        db2 = TestingSessionLocal()
        try:
            from app.models.notification import Notification, NotificationType
            notifs = db2.query(Notification).filter(
                Notification.user_id == user.user_id,
                Notification.type == NotificationType.quota_increase,
            ).all()
            assert len(notifs) == 1, f"Expected 1 notification, got {len(notifs)}"
            notif = notifs[0]
            assert "50" in notif.content, f"通知内容未包含增加额度: {notif.content}"
            assert "150" in notif.content, f"通知内容未包含新额度: {notif.content}"
        finally:
            db2.close()

    def test_quota_decrease_creates_notification(self):
        """管理员减少额度，DB 中存在 quota_decrease 通知，内容含减少额度"""
        db = TestingSessionLocal()
        try:
            admin = _create_admin(db)
            user = _create_user(db, "dec_user", "dec@test.com", quota=100)
            db.commit()
            user_id = user.user_id
        finally:
            db.close()

        token = self._admin_token()
        resp = client.post(
            f"/api/v1/admin/users/{user_id}/quota",
            json={"amount": -30, "reason": "correction"},
            headers={"Authorization": f"Bearer {token}"},
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["new_quota"] == 70

        # 验证 DB 中有 quota_decrease 通知
        db2 = TestingSessionLocal()
        try:
            from app.models.notification import Notification, NotificationType
            notifs = db2.query(Notification).filter(
                Notification.user_id == user.user_id,
                Notification.type == NotificationType.quota_decrease,
            ).all()
            assert len(notifs) == 1, f"Expected 1 notification, got {len(notifs)}"
            notif = notifs[0]
            assert "30" in notif.content, f"通知内容未包含减少额度: {notif.content}"
            assert "70" in notif.content, f"通知内容未包含剩余额度: {notif.content}"
        finally:
            db2.close()

    def test_quota_adjust_notification_contains_reason(self):
        """验证 metadata 中包含操作原因"""
        db = TestingSessionLocal()
        try:
            admin = _create_admin(db)
            user = _create_user(db, "reason_user", "reason@test.com", quota=200)
            db.commit()
            user_id = user.user_id
        finally:
            db.close()

        token = self._admin_token()
        resp = client.post(
            f"/api/v1/admin/users/{user_id}/quota",
            json={"amount": 25, "reason": "monthly bonus"},
            headers={"Authorization": f"Bearer {token}"},
        )
        assert resp.status_code == 200

        db2 = TestingSessionLocal()
        try:
            from app.models.notification import Notification, NotificationType
            import json
            notif = db2.query(Notification).filter(
                Notification.user_id == user.user_id,
                Notification.type == NotificationType.quota_increase,
            ).first()
            assert notif is not None, "通知不存在"
            extra = json.loads(notif.extra_data) if notif.extra_data else {}
            # operator 字段应存在于 metadata 中
            assert "operator" in extra, f"metadata 中缺少 operator: {extra}"
        finally:
            db2.close()

    def test_quota_adjust_response_unaffected(self):
        """通知发送失败时 API 仍返回 new_quota"""
        import unittest.mock as mock

        db = TestingSessionLocal()
        try:
            admin = _create_admin(db)
            user = _create_user(db, "resp_user", "resp@test.com", quota=100)
            db.commit()
            user_id = user.user_id
        finally:
            db.close()

        token = self._admin_token()
        with mock.patch("app.services.notification_service.create_notification", side_effect=Exception("mocked error")):
            resp = client.post(
                f"/api/v1/admin/users/{user_id}/quota",
                json={"amount": 20, "reason": "test"},
                headers={"Authorization": f"Bearer {token}"},
            )
        assert resp.status_code == 200, f"Expected 200, got {resp.status_code}: {resp.json()}"
        data = resp.json()
        assert "new_quota" in data, f"响应缺少 new_quota 字段: {data}"
        assert data["new_quota"] == 120
