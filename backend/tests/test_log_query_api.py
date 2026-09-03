"""日志查询API测试"""
import json
import pytest
from datetime import datetime, timedelta
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.main import app
from app.core.database import Base, get_db
from app.models.user import User, UserRole, UserStatus
from app.models.operation_log import OperationLog
from app.models.login_log import LoginLog
from app.core.security import hash_password_sha256

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


def _create_admin(db, username="admin", email="admin@example.com"):
    """创建管理员用户"""
    admin = User(
        user_id=f"usr_{username}",
        username=username,
        email=email,
        password=hash_password_sha256("adminpass"),
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
        password=hash_password_sha256("userpass"),
        role=UserRole.user,
        status=UserStatus.active,
    )
    db.add(user)
    db.commit()
    return user


def _admin_token():
    """获取管理员token（通过模拟登录）"""
    # 使用直接请求方式，让TestClient帮我们处理
    response = client.post(
        "/api/v1/auth/login",
        data={"username": "admin", "password": hash_password_sha256("adminpass")},
    )
    if response.status_code == 200:
        return response.json().get("access_token")
    return None


def _user_token():
    """获取普通用户token"""
    response = client.post(
        "/api/v1/auth/login",
        data={"username": "user1", "password": hash_password_sha256("userpass")},
    )
    if response.status_code == 200:
        return response.json().get("access_token")
    return None


class TestOperationLogsNonAdmin:
    """非管理员调用操作日志接口 → 403"""

    def test_non_admin_get_operations_403(self):
        db = TestingSessionLocal()
        try:
            _create_admin(db)
            _create_regular_user(db)
            db.commit()
        finally:
            db.close()

        token = _user_token()
        assert token is not None, "Failed to get user token"
        response = client.get(
            "/api/v1/admin/logs/operations",
            headers={"Authorization": f"Bearer {token}"},
        )
        assert response.status_code == 403


class TestOperationLogsAdmin:
    """管理员调用操作日志接口 → 200，数据格式正确"""

    def test_admin_get_operations_200_shape(self):
        db = TestingSessionLocal()
        try:
            admin = _create_admin(db)
            op_log = OperationLog(
                log_id="log_op_001",
                operator_id=admin.user_id,
                operator_name=admin.username,
                action="create",
                target_type="user",
                target_id="usr_target",
                detail=json.dumps({"key": "value"}),
                ip_address="1.2.3.4",
            )
            db.add(op_log)
            db.commit()
        finally:
            db.close()

        token = _admin_token()
        assert token is not None, "Failed to get admin token"
        response = client.get(
            "/api/v1/admin/logs/operations",
            headers={"Authorization": f"Bearer {token}"},
        )
        assert response.status_code == 200
        data = response.json()
        assert "total" in data
        assert "items" in data
        assert isinstance(data["items"], list)
        assert data["total"] == 1
        item = data["items"][0]
        assert item["log_id"] == "log_op_001"
        assert item["operator_name"] == admin.username
        assert item["detail"] == {"key": "value"}

    def test_keyword_filter_operator_name(self):
        db = TestingSessionLocal()
        try:
            admin = _create_admin(db)
            db.add(OperationLog(
                log_id="log_op_001",
                operator_id=admin.user_id,
                operator_name="Alice",
                action="create",
                target_type="user",
                detail="{}",
            ))
            db.add(OperationLog(
                log_id="log_op_002",
                operator_id=admin.user_id,
                operator_name="Bob",
                action="delete",
                target_type="user",
                detail="{}",
            ))
            db.commit()
        finally:
            db.close()

        token = _admin_token()
        response = client.get(
            "/api/v1/admin/logs/operations?keyword=Alice",
            headers={"Authorization": f"Bearer {token}"},
        )
        assert response.status_code == 200
        data = response.json()
        assert data["total"] == 1
        assert data["items"][0]["operator_name"] == "Alice"

    def test_keyword_filter_detail(self):
        db = TestingSessionLocal()
        try:
            admin = _create_admin(db)
            db.add(OperationLog(
                log_id="log_op_001",
                operator_id=admin.user_id,
                operator_name="Alice",
                action="create",
                target_type="user",
                detail=json.dumps({"note": "important change"}),
            ))
            db.add(OperationLog(
                log_id="log_op_002",
                operator_id=admin.user_id,
                operator_name="Bob",
                action="create",
                target_type="user",
                detail=json.dumps({"note": "minor edit"}),
            ))
            db.commit()
        finally:
            db.close()

        token = _admin_token()
        response = client.get(
            "/api/v1/admin/logs/operations?keyword=important",
            headers={"Authorization": f"Bearer {token}"},
        )
        assert response.status_code == 200
        data = response.json()
        assert data["total"] == 1
        assert data["items"][0]["log_id"] == "log_op_001"
        assert data["items"][0]["detail"] == {"note": "important change"}

    def test_date_filter(self):
        db = TestingSessionLocal()
        try:
            admin = _create_admin(db)
            db.add(OperationLog(
                log_id="log_op_001",
                operator_id=admin.user_id,
                operator_name=admin.username,
                action="create",
                target_type="user",
                detail="{}",
                created_at=datetime(2024, 1, 15, 12, 0, 0),
            ))
            db.add(OperationLog(
                log_id="log_op_002",
                operator_id=admin.user_id,
                operator_name=admin.username,
                action="delete",
                target_type="user",
                detail="{}",
                created_at=datetime(2024, 3, 15, 12, 0, 0),
            ))
            db.commit()
        finally:
            db.close()

        token = _admin_token()
        response = client.get(
            "/api/v1/admin/logs/operations?start_date=2024-01-01&end_date=2024-01-31",
            headers={"Authorization": f"Bearer {token}"},
        )
        assert response.status_code == 200
        data = response.json()
        assert data["total"] == 1
        assert data["items"][0]["log_id"] == "log_op_001"

    def test_action_filter(self):
        db = TestingSessionLocal()
        try:
            admin = _create_admin(db)
            db.add(OperationLog(
                log_id="log_op_001",
                operator_id=admin.user_id,
                operator_name=admin.username,
                action="create",
                target_type="user",
                detail="{}",
            ))
            db.add(OperationLog(
                log_id="log_op_002",
                operator_id=admin.user_id,
                operator_name=admin.username,
                action="delete",
                target_type="user",
                detail="{}",
            ))
            db.add(OperationLog(
                log_id="log_op_003",
                operator_id=admin.user_id,
                operator_name=admin.username,
                action="delete",
                target_type="provider",
                detail="{}",
            ))
            db.commit()
        finally:
            db.close()

        token = _admin_token()
        response = client.get(
            "/api/v1/admin/logs/operations?action=delete",
            headers={"Authorization": f"Bearer {token}"},
        )
        assert response.status_code == 200
        data = response.json()
        assert data["total"] == 2
        for item in data["items"]:
            assert item["action"] == "delete"

    def test_pagination(self):
        db = TestingSessionLocal()
        try:
            admin = _create_admin(db)
            for i in range(25):
                db.add(OperationLog(
                    log_id=f"log_op_{i:03d}",
                    operator_id=admin.user_id,
                    operator_name=admin.username,
                    action="create",
                    target_type="user",
                    detail="{}",
                ))
            db.commit()
        finally:
            db.close()

        token = _admin_token()
        # Page 1
        response = client.get(
            "/api/v1/admin/logs/operations?page=1&page_size=10",
            headers={"Authorization": f"Bearer {token}"},
        )
        assert response.status_code == 200
        data = response.json()
        assert data["total"] == 25
        assert len(data["items"]) == 10

        # Page 2
        response = client.get(
            "/api/v1/admin/logs/operations?page=2&page_size=10",
            headers={"Authorization": f"Bearer {token}"},
        )
        assert response.status_code == 200
        data = response.json()
        assert data["total"] == 25
        assert len(data["items"]) == 10


class TestLoginLogsNonAdmin:
    """非管理员调用登录日志接口 → 403"""

    def test_non_admin_get_logins_403(self):
        db = TestingSessionLocal()
        try:
            _create_admin(db)
            _create_regular_user(db)
            db.commit()
        finally:
            db.close()

        token = _user_token()
        assert token is not None, "Failed to get user token"
        response = client.get(
            "/api/v1/admin/logs/logins",
            headers={"Authorization": f"Bearer {token}"},
        )
        assert response.status_code == 403


class TestLoginLogsAdmin:
    """管理员调用登录日志接口 → 200，数据格式正确"""

    def test_admin_get_logins_200_shape(self):
        db = TestingSessionLocal()
        try:
            _create_admin(db)
            login_log = LoginLog(
                log_id="log_login_001",
                username="alice",
                user_id="usr_alice",
                ip_address="1.2.3.4",
                user_agent="TestBrowser/1.0",
                status="success",
            )
            db.add(login_log)
            db.commit()
        finally:
            db.close()

        token = _admin_token()
        assert token is not None, "Failed to get admin token"
        response = client.get(
            "/api/v1/admin/logs/logins",
            headers={"Authorization": f"Bearer {token}"},
        )
        assert response.status_code == 200
        data = response.json()
        assert "total" in data
        assert "items" in data
        assert data["total"] == 1
        item = data["items"][0]
        assert item["log_id"] == "log_login_001"
        assert item["username"] == "alice"
        assert item["status"] == "success"

    def test_keyword_filter_username(self):
        db = TestingSessionLocal()
        try:
            _create_admin(db)
            db.add(LoginLog(log_id="log_login_001", username="alice_test", status="success"))
            db.add(LoginLog(log_id="log_login_002", username="bob_test", status="failed"))
            db.add(LoginLog(log_id="log_login_003", username="alice_other", status="success"))
            db.commit()
        finally:
            db.close()

        token = _admin_token()
        response = client.get(
            "/api/v1/admin/logs/logins?keyword=alice",
            headers={"Authorization": f"Bearer {token}"},
        )
        assert response.status_code == 200
        data = response.json()
        assert data["total"] == 2
        for item in data["items"]:
            assert "alice" in item["username"].lower()

    def test_date_filter(self):
        db = TestingSessionLocal()
        try:
            _create_admin(db)
            db.add(LoginLog(
                log_id="log_login_001",
                username="alice",
                status="success",
                created_at=datetime(2024, 1, 15, 12, 0, 0),
            ))
            db.add(LoginLog(
                log_id="log_login_002",
                username="bob",
                status="failed",
                created_at=datetime(2024, 6, 15, 12, 0, 0),
            ))
            db.commit()
        finally:
            db.close()

        token = _admin_token()
        response = client.get(
            "/api/v1/admin/logs/logins?start_date=2024-01-01&end_date=2024-01-31",
            headers={"Authorization": f"Bearer {token}"},
        )
        assert response.status_code == 200
        data = response.json()
        assert data["total"] == 1
        assert data["items"][0]["log_id"] == "log_login_001"

    def test_status_filter(self):
        db = TestingSessionLocal()
        try:
            _create_admin(db)
            db.add(LoginLog(log_id="log_login_001", username="alice", status="success"))
            db.add(LoginLog(log_id="log_login_002", username="bob", status="failed"))
            db.add(LoginLog(log_id="log_login_003", username="carol", status="blocked"))
            db.commit()
        finally:
            db.close()

        token = _admin_token()
        response = client.get(
            "/api/v1/admin/logs/logins?status=failed",
            headers={"Authorization": f"Bearer {token}"},
        )
        assert response.status_code == 200
        data = response.json()
        assert data["total"] == 1
        assert data["items"][0]["status"] == "failed"


class TestOperationLogsMalformedDetail:
    """detail 字段为非 JSON 字符串时，接口应降级返回原字符串，不影响响应整体性"""

    def test_malformed_detail_returns_raw_string(self):
        db = TestingSessionLocal()
        try:
            admin = _create_admin(db)
            db.add(OperationLog(
                log_id="log_op_malformed",
                operator_id=admin.user_id,
                operator_name=admin.username,
                action="create",
                target_type="user",
                detail="not valid json",  # 故意写入非 JSON 字符串
                ip_address="1.2.3.4",
            ))
            db.commit()
        finally:
            db.close()

        token = _admin_token()
        assert token is not None, "Failed to get admin token"
        response = client.get(
            "/api/v1/admin/logs/operations",
            headers={"Authorization": f"Bearer {token}"},
        )
        assert response.status_code == 200
        data = response.json()
        assert data["total"] == 1
        item = data["items"][0]
        assert item["log_id"] == "log_op_malformed"
        # 降级：json.loads 失败时,服务器返回原始字符串
        assert item["detail"] == "not valid json"
