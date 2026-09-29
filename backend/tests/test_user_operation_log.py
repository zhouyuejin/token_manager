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
import os
import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.main import app
from app.core.database import Base, get_db
from app.dependencies import get_current_user
from app.models.user import User, UserRole, UserStatus
from app.models.operation_log import OperationLog
from app.models.api_key import ApiKey
from app.models.organization import Department
from app.models.project import Project, UserProject
from app.core.security import hash_password_sha256

# SQLite in-memory 多 connection 互不可见；强制单 connection 共享表。
engine = create_engine(
    "sqlite:///:memory:",
    connect_args={"check_same_thread": False},

)

# 内存 SQLite 测试库
TEST_DATABASE_URL = os.environ.get("TEST_DATABASE_URL", "mysql+pymysql://token_user:token_password@mysql:3306/token_db_test?charset=utf8mb4")
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
    db = TestingSessionLocal()
    try:
        for table in reversed(Base.metadata.sorted_tables):
            db.execute(__import__("sqlalchemy").text("SET FOREIGN_KEY_CHECKS=0"))
            db.execute(__import__("sqlalchemy").text(f"TRUNCATE TABLE {table.name}"))
            db.execute(__import__("sqlalchemy").text("SET FOREIGN_KEY_CHECKS=1"))
        db.commit()
    finally:
        db.close()
    yield


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
    db.add(Department(dept_id='dept_alice', name='部门'))
    db.flush()
    db.add(Project(project_id='project_alice', dept_id='dept_alice', name='项目', owner_user_id=user.user_id))
    db.flush()
    db.add(UserProject(user_id=user.user_id, project_id='project_alice'))
    db.commit()
    return user


def _get_user_token(username="alice", password="alicepass1"):
    app.dependency_overrides[get_db] = override_get_db
    app.dependency_overrides.pop(get_current_user, None)
    db = TestingSessionLocal()
    try:
        _create_regular_user(db, username=username, password=password)
    finally:
        db.close()
    response = client.post(
        "/api/v1/auth/login",
        data={"username": username, "password": hash_password_sha256(password)},
    )
    assert response.status_code == 200, response.text
    return response.json()["access_token"]


def _persist_key(name):
    db = TestingSessionLocal()
    try:
        user = db.query(User).filter_by(username='alice').one()
        key = ApiKey(key_id='key_test', user_id=user.user_id, api_key='tmk_test',
                     key_name=name, project_id='project_alice')
        db.add(key)
        db.commit()
        return key.key_id
    finally:
        db.close()


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
                "project_id": "project_alice",
            },
        )
        assert response.status_code == 200
        request_id = response.json()["request_id"]

        db = TestingSessionLocal()
        try:
            log = db.query(OperationLog).filter(
                OperationLog.action == "approval_created",
                OperationLog.target_type == "approval_request",
            ).first()
            assert log is not None, "API Key 申请未埋点"
            assert log.operator_name == "alice"
            assert log.target_id == request_id
            detail = json.loads(log.detail)
            assert detail["request_type"] == "api_key"
        finally:
            db.close()


class TestUpdateApiKeyLogs:
    """PUT /api-keys/{key_id} -> OperationLog action="update", detail = changed fields only"""

    def _create_key(self, headers):
        return _persist_key('orig-name')

    def test_update_api_key_records_log(self):
        token = _get_user_token()
        headers = {"Authorization": f"Bearer {token}"}
        key_id = self._create_key(headers)

        response = client.put(
            f"/api/v1/api-keys/{key_id}",
            headers=headers,
            json={"name": "new-name"},
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
            assert detail == {"name": "new-name"}
        finally:
            db.close()


class TestUpdateApiKeyStatusLogs:
    """PUT /api-keys/{key_id}/status -> OperationLog action="update_status", target_type="api_key\""""

    def test_disable_api_key_records_log(self):
        token = _get_user_token()
        headers = {"Authorization": f"Bearer {token}"}
        key_id = _persist_key('to-disable')

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
            assert detail["new"] == "disabled"
        finally:
            db.close()


class TestDeleteApiKeyLogs:
    """DELETE /api-keys/{key_id} -> OperationLog action="delete", target_type="api_key\""""

    def test_delete_api_key_records_log(self):
        token = _get_user_token()
        headers = {"Authorization": f"Bearer {token}"}
        key_id = _persist_key('to-delete')

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
