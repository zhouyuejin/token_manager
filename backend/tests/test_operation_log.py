"""操作日志单元测试"""
import json
import pytest
from unittest.mock import patch, MagicMock
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.main import app
from app.core.database import Base, get_db
from app.models.user import User, UserRole, UserStatus
from app.models.operation_log import OperationLog
from app.core.security import get_password_hash

# 内存 SQLite 测试库
TEST_DATABASE_URL = "sqlite:///:memory:"
engine = create_engine(TEST_DATABASE_URL, connect_args={"check_same_thread": False})
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


def _create_admin(db, username="admin", email="admin@example.com", password="adminpass"):
    """创建管理员用户"""
    admin = User(
        user_id=f"usr_{username}",
        username=username,
        email=email,
        password=get_password_hash(password),
        role=UserRole.admin,
        status=UserStatus.active,
    )
    db.add(admin)
    db.commit()
    return admin


def _create_regular_user(db, username="user1", email="user1@example.com"):
    """创建普通用户"""
    user = User(
        user_id=f"usr_{username}",
        username=username,
        email=email,
        password=get_password_hash("userpass1"),
        role=UserRole.user,
        status=UserStatus.active,
        quota=1000,
    )
    db.add(user)
    db.commit()
    return user


def _get_admin_token():
    """获取管理员token"""
    db = TestingSessionLocal()
    try:
        _create_admin(db)
    finally:
        db.close()
    response = client.post(
        "/api/v1/auth/login",
        data={"username": "admin", "password": "adminpass"},
    )
    return response.json()["access_token"]


class TestCreateUserOperationLog:
    """POST /admin/users → OperationLog entry exists with all fields correct, detail contains username"""

    def test_create_user_logs_correctly(self):
        token = _get_admin_token()
        headers = {"Authorization": f"Bearer {token}"}

        response = client.post(
            "/api/v1/admin/users",
            headers=headers,
            json={
                "username": "newuser",
                "email": "newuser@example.com",
                "password": "newpass123",
                "role": "user",
                "quota": 5000,
            },
        )
        assert response.status_code == 200
        data = response.json()
        user_id = data["user_id"]

        db = TestingSessionLocal()
        try:
            log = db.query(OperationLog).filter(
                OperationLog.target_id == user_id,
                OperationLog.action == "create",
            ).first()
            assert log is not None
            assert log.operator_name == "admin"
            assert log.action == "create"
            assert log.target_type == "user"
            assert log.target_id == user_id
            assert log.ip_address is not None

            detail = json.loads(log.detail)
            assert detail["username"] == "newuser"
            assert detail["email"] == "newuser@example.com"
            assert detail["role"] == "user"
            assert detail["quota"] == 5000
        finally:
            db.close()


class TestUpdateUserQuotaOperationLog:
    """PUT /admin/users/{id} updating only quota → OperationLog.detail has exactly one key "quota\""""

    def test_update_user_quota_only_logs_quota(self):
        token = _get_admin_token()
        headers = {"Authorization": f"Bearer {token}"}

        # 先创建一个普通用户
        db = TestingSessionLocal()
        try:
            user = _create_regular_user(db)
            user_id = user.user_id
        finally:
            db.close()

        # 只更新 quota
        response = client.put(
            f"/api/v1/admin/users/{user_id}",
            headers=headers,
            json={"quota": 9999},
        )
        assert response.status_code == 200

        db = TestingSessionLocal()
        try:
            log = db.query(OperationLog).filter(
                OperationLog.target_id == user_id,
                OperationLog.action == "update",
            ).first()
            assert log is not None
            detail = json.loads(log.detail)
            assert detail == {"quota": 9999}
        finally:
            db.close()


class TestDeleteUserOperationLog:
    """DELETE /admin/users/{id} → OperationLog action="delete", target_id = deleted user's user_id"""

    def test_delete_user_logs_correctly(self):
        token = _get_admin_token()
        headers = {"Authorization": f"Bearer {token}"}

        # 先创建一个普通用户
        db = TestingSessionLocal()
        try:
            user = _create_regular_user(db, "deluser", "deluser@example.com")
            user_id = user.user_id
        finally:
            db.close()

        response = client.delete(
            f"/api/v1/admin/users/{user_id}",
            headers=headers,
        )
        assert response.status_code == 200

        db = TestingSessionLocal()
        try:
            log = db.query(OperationLog).filter(
                OperationLog.target_id == user_id,
                OperationLog.action == "delete",
            ).first()
            assert log is not None
            assert log.action == "delete"
            assert log.target_type == "user"
            assert log.target_id == user_id
            detail = json.loads(log.detail)
            assert detail["username"] == "deluser"
        finally:
            db.close()


class TestChineseCharacterDetail:
    """record_operation with Chinese characters in detail → no Unicode escape in stored text"""

    def test_chinese_detail_stored_as_utf8(self):
        from app.services.operation_log_service import record_operation

        db = TestingSessionLocal()
        try:
            admin = _create_admin(db, "admin2", "admin2@example.com")

            record_operation(
                db=db,
                operator=admin,
                action="update",
                target_type="user",
                target_id="usr_test",
                detail={"reason": "测试中文备注", "操作人": "管理员"},
                ip_address="1.2.3.4",
            )

            log = db.query(OperationLog).filter(
                OperationLog.target_id == "usr_test"
            ).first()
            assert log is not None
            # ensure_ascii=False 保证中文不被转义为 \u...
            assert "\\u" not in log.detail
            detail = json.loads(log.detail)
            assert detail["reason"] == "测试中文备注"
            assert detail["操作人"] == "管理员"
        finally:
            db.close()


class TestRecordOperationDBFailure:
    """record_operation when DB commit fails → does NOT raise"""

    def test_record_operation_db_failure_no_raise(self):
        from app.services.operation_log_service import record_operation

        db = TestingSessionLocal()
        try:
            admin = _create_admin(db, "admin3", "admin3@example.com")

            # Simulate a DB failure by patching _create_login_log style
            # We patch db.commit to raise
            with patch.object(db, "commit", side_effect=Exception("DB write error")):
                # Should not raise — fire-and-forget
                record_operation(
                    db=db,
                    operator=admin,
                    action="create",
                    target_type="user",
                    target_id="usr_fail",
                    detail={"test": "data"},
                    ip_address="1.2.3.4",
                )
            # If we get here without exception, the test passes
            assert True
        finally:
            db.close()


class TestMultipleActionsAndTargetTypes:
    """Cover at least create / update / delete and at least two target_types"""

    def test_provider_create_log(self):
        token = _get_admin_token()
        headers = {"Authorization": f"Bearer {token}"}

        response = client.post(
            "/api/v1/admin/providers",
            headers=headers,
            json={
                "name": "TestProvider",
                "type": "openai",
                "endpoint": "https://api.test.com",
                "api_key": "sk-testkey",
                "priority": 50,
                "timeout": 30,
                "quota_hourly": 1000,
                "quota_weekly": 5000,
            },
        )
        assert response.status_code == 200
        data = response.json()
        provider_id = data["provider_id"]

        db = TestingSessionLocal()
        try:
            log = db.query(OperationLog).filter(
                OperationLog.target_id == provider_id,
                OperationLog.action == "create",
            ).first()
            assert log is not None
            assert log.target_type == "provider"
            assert log.operator_name == "admin"
            detail = json.loads(log.detail)
            assert detail["name"] == "TestProvider"
            assert detail["type"] == "openai"
            assert detail["endpoint"] == "https://api.test.com"
            # api_key should NOT be in detail (sensitive)
            assert "api_key" not in detail
        finally:
            db.close()

    def test_model_mapping_create_log(self):
        token = _get_admin_token()
        headers = {"Authorization": f"Bearer {token}"}

        # 先创建一个 provider
        p_resp = client.post(
            "/api/v1/admin/providers",
            headers=headers,
            json={
                "name": "MMProvider",
                "type": "openai",
                "endpoint": "https://api.mm.com",
                "api_key": "sk-mm",
            },
        )
        provider_id = p_resp.json()["provider_id"]

        response = client.post(
            "/api/v1/admin/models",
            headers=headers,
            json={
                "model_id": "mmodel_001",
                "display_name": "TestModel",
                "provider_id": provider_id,
                "provider_model": "gpt-4",
                "aliases": "test-gpt4",
            },
        )
        assert response.status_code == 200
        model_id = response.json()["model_id"]

        db = TestingSessionLocal()
        try:
            log = db.query(OperationLog).filter(
                OperationLog.target_id == model_id,
                OperationLog.action == "create",
            ).first()
            assert log is not None
            assert log.target_type == "model_mapping"
            detail = json.loads(log.detail)
            assert detail["display_name"] == "TestModel"
            assert detail["provider_id"] == provider_id
            assert detail["provider_model"] == "gpt-4"
        finally:
            db.close()
