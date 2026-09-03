"""普通用户写接口的操作日志埋点测试

覆盖 6 个新埋点：
- PUT /users/me/password              -> action="change_password"
- PUT /users/me/notification-settings -> action="update", target_type="notification_settings"
- POST /api-keys                      -> action="create", target_type="api_key"
- PUT /api-keys/{key_id}              -> action="update", target_type="api_key"
- PUT /api-keys/{key_id}/status       -> action="update_status", target_type="api_key"
- DELETE /api-keys/{key_id}           -> action="delete", target_type="api_key"
"""
import json
import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.main import app
from app.core.database import Base, get_db
from app.models.user import User, UserRole, UserStatus
from app.models.operation_log import OperationLog
from app.core.security import hash_password_sha256

# SQLite in-memory 多 connection 互不可见；强制单 connection 共享表。
engine = create_engine(
    "sqlite:///:memory:",
    connect_args={"check_same_thread": False},
    poolclass=StaticPool,
)

# 内存 SQLite 测试库
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


@pytest.fixture(autouse=True)
def setup_db():
    Base.metadata.create_all(bind=engine)
    yield
    Base.metadata.drop_all(bind=engine)


def _create_regular_user(db, username="alice", email="alice@example.com", password="alicepass1"):
    user = User(
        user_id=f"usr_{username}",
        username=username,
        email=email,
        password=hash_password_sha256(password),
        role=UserRole.user,
        status=UserStatus.active,
        quota=1000,
    )
    db.add(user)
    db.commit()
    return user


def _get_user_token(username="alice", password="alicepass1"):
    db = TestingSessionLocal()
    try:
        _create_regular_user(db, username=username, password=password)
    finally:
        db.close()
    response = client.post(
        "/api/v1/auth/login",
        data={"username": username, "password": hash_password_sha256(password)},
    )
    return response.json()["access_token"]


class TestChangePasswordLogs:
    """PUT /users/me/password -> OperationLog action="change_password", operator = self"""

    def test_change_password_records_log(self):
        token = _get_user_token()
        headers = {"Authorization": f"Bearer {token}"}

        response = client.put(
            "/api/v1/users/me/password",
            headers=headers,
            json={"old_password": hash_password_sha256("alicepass1"), "new_password": hash_password_sha256("alicepass2")},
        )
        assert response.status_code == 200

        db = TestingSessionLocal()
        try:
            log = db.query(OperationLog).filter(
                OperationLog.action == "change_password",
            ).first()
            assert log is not None, "change_password 操作未埋点"
            assert log.target_type == "user"
            assert log.operator_name == "alice"
            assert log.operator_id == "usr_alice"
            assert log.target_id == "usr_alice"
            assert log.ip_address is not None
        finally:
            db.close()


class TestUpdateNotificationSettingsLogs:
    """PUT /users/me/notification-settings -> OperationLog action="update", target_type="notification_settings\""""

    def test_update_notification_settings_records_log(self):
        token = _get_user_token()
        headers = {"Authorization": f"Bearer {token}"}

        response = client.put(
            "/api/v1/users/me/notification-settings",
            headers=headers,
            json={
                "quota_low_alert": False,
                "quota_change_alert": True,
                "daily_report": True,
            },
        )
        assert response.status_code == 200

        db = TestingSessionLocal()
        try:
            log = db.query(OperationLog).filter(
                OperationLog.target_type == "notification_settings",
            ).first()
            assert log is not None, "通知设置更新未埋点"
            assert log.action == "update"
            assert log.operator_name == "alice"
            assert log.target_id == "usr_alice"
            assert log.ip_address is not None
            detail = json.loads(log.detail)
            assert detail["quota_low_alert"] is False
            assert detail["quota_change_alert"] is True
            assert detail["daily_report"] is True
        finally:
            db.close()


class TestCreateApiKeyLogs:
    """POST /api-keys -> OperationLog action="create", target_type="api_key", target_id = new key_id"""

    def test_create_api_key_records_log(self):
        token = _get_user_token()
        headers = {"Authorization": f"Bearer {token}"}

        response = client.post(
            "/api/v1/api-keys",
            headers=headers,
            json={
                "name": "my-key",
                "daily_limit": 100,
                "monthly_limit": 1000,
                "qps_limit": 5,
            },
        )
        assert response.status_code == 200
        key_id = response.json()["key_id"]

        db = TestingSessionLocal()
        try:
            log = db.query(OperationLog).filter(
                OperationLog.action == "create",
                OperationLog.target_type == "api_key",
            ).first()
            assert log is not None, "创建 API Key 未埋点"
            assert log.operator_name == "alice"
            assert log.target_id == key_id
            assert log.ip_address is not None
            detail = json.loads(log.detail)
            assert detail["name"] == "my-key"
            assert detail["daily_limit"] == 100
            assert detail["monthly_limit"] == 1000
            assert detail["qps_limit"] == 5
            # 敏感字段 api_key 明文不应出现在详情里
            assert "api_key" not in detail
        finally:
            db.close()


class TestUpdateApiKeyLogs:
    """PUT /api-keys/{key_id} -> OperationLog action="update", detail = changed fields only"""

    def _create_key(self, headers):
        resp = client.post(
            "/api/v1/api-keys",
            headers=headers,
            json={"name": "orig-name", "daily_limit": 10, "monthly_limit": 100, "qps_limit": 1},
        )
        assert resp.status_code == 200
        return resp.json()["key_id"]

    def test_update_api_key_records_log(self):
        token = _get_user_token()
        headers = {"Authorization": f"Bearer {token}"}
        key_id = self._create_key(headers)

        response = client.put(
            f"/api/v1/api-keys/{key_id}",
            headers=headers,
            json={"name": "new-name", "qps_limit": 20},
        )
        assert response.status_code == 200

        db = TestingSessionLocal()
        try:
            log = db.query(OperationLog).filter(
                OperationLog.action == "update",
                OperationLog.target_type == "api_key",
                OperationLog.target_id == key_id,
            ).first()
            assert log is not None, "更新 API Key 未埋点"
            assert log.operator_name == "alice"
            assert log.ip_address is not None
            detail = json.loads(log.detail)
            assert detail == {"name": "new-name", "qps_limit": 20}
        finally:
            db.close()


class TestUpdateApiKeyStatusLogs:
    """PUT /api-keys/{key_id}/status -> OperationLog action="update_status", target_type="api_key\""""

    def test_disable_api_key_records_log(self):
        token = _get_user_token()
        headers = {"Authorization": f"Bearer {token}"}
        create_resp = client.post(
            "/api/v1/api-keys",
            headers=headers,
            json={"name": "to-disable"},
        )
        key_id = create_resp.json()["key_id"]

        response = client.put(
            f"/api/v1/api-keys/{key_id}/status",
            headers=headers,
            json={"status": "disabled"},
        )
        assert response.status_code == 200

        db = TestingSessionLocal()
        try:
            log = db.query(OperationLog).filter(
                OperationLog.action == "update_status",
                OperationLog.target_type == "api_key",
                OperationLog.target_id == key_id,
            ).first()
            assert log is not None, "更新 API Key 状态未埋点"
            assert log.operator_name == "alice"
            assert log.ip_address is not None
            detail = json.loads(log.detail)
            assert detail["status"] == "disabled"
        finally:
            db.close()


class TestDeleteApiKeyLogs:
    """DELETE /api-keys/{key_id} -> OperationLog action="delete", target_type="api_key\""""

    def test_delete_api_key_records_log(self):
        token = _get_user_token()
        headers = {"Authorization": f"Bearer {token}"}
        create_resp = client.post(
            "/api/v1/api-keys",
            headers=headers,
            json={"name": "to-delete"},
        )
        key_id = create_resp.json()["key_id"]

        response = client.delete(
            f"/api/v1/api-keys/{key_id}",
            headers=headers,
        )
        assert response.status_code == 200

        db = TestingSessionLocal()
        try:
            log = db.query(OperationLog).filter(
                OperationLog.action == "delete",
                OperationLog.target_type == "api_key",
                OperationLog.target_id == key_id,
            ).first()
            assert log is not None, "删除 API Key 未埋点"
            assert log.operator_name == "alice"
            assert log.ip_address is not None
            detail = json.loads(log.detail)
            assert detail["name"] == "to-delete"
        finally:
            db.close()
