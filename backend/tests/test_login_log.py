"""登录日志单元测试"""
import pytest
from unittest.mock import patch, MagicMock
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.main import app
from app.core.database import Base, get_db
from app.models.user import User, UserRole, UserStatus
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


def _create_user(db, username, email, password="hashedpwd", status=UserStatus.active):
    """创建测试用户并提交。"""
    from app.core.security import generate_user_id
    user = User(
        user_id=generate_user_id(),
        username=username,
        email=email,
        password=hash_password_sha256(password),
        role=UserRole.user,
        status=status,
    )
    db.add(user)
    db.commit()
    return user


class TestLoginLogSuccess:
    """成功登录 → 数据库新增一行，status=success，user_id 正确，username 正确，ip 非空"""

    def test_success_login_creates_log(self):
        from app.models.login_log import LoginLog
        db = TestingSessionLocal()
        try:
            user = _create_user(db, "alice", "alice@example.com", password="secret123")
            db.commit()

            from app.api.v1.auth import _create_login_log
            _create_login_log(db, "alice", user.user_id, "1.2.3.4", "TestBrowser/1.0", "success")

            log = db.query(LoginLog).filter(LoginLog.username == "alice").first()
            assert log is not None
            assert log.status == "success"
            assert log.user_id == user.user_id
            assert log.username == "alice"
            assert log.ip_address == "1.2.3.4"
            assert log.user_agent == "TestBrowser/1.0"
            assert log.log_id is not None
            assert len(log.log_id) == 32
        finally:
            db.close()


class TestLoginLogFailureReasons:
    """用户名错误 / 密码错误 / 禁用账号"""

    def test_user_not_found(self):
        from app.models.login_log import LoginLog
        db = TestingSessionLocal()
        try:
            from app.api.v1.auth import _create_login_log
            _create_login_log(db, "nobody", None, "1.2.3.4", "TestBrowser/1.0", "failed", "user_not_found")

            log = db.query(LoginLog).filter(LoginLog.username == "nobody").first()
            assert log is not None
            assert log.status == "failed"
            assert log.failure_reason == "user_not_found"
            assert log.user_id is None
        finally:
            db.close()

    def test_invalid_password(self):
        from app.models.login_log import LoginLog
        db = TestingSessionLocal()
        try:
            user = _create_user(db, "bob", "bob@example.com", password="correctpwd")
            db.commit()

            from app.api.v1.auth import _create_login_log
            _create_login_log(db, "bob", user.user_id, "5.6.7.8", "Bot/2.0", "failed", "invalid_password")

            log = db.query(LoginLog).filter(LoginLog.username == "bob").first()
            assert log is not None
            assert log.status == "failed"
            assert log.failure_reason == "invalid_password"
            assert log.user_id == user.user_id
        finally:
            db.close()

    def test_account_disabled(self):
        from app.models.login_log import LoginLog
        db = TestingSessionLocal()
        try:
            user = _create_user(db, "charlie", "charlie@example.com", status=UserStatus.disabled)
            db.commit()

            from app.api.v1.auth import _create_login_log
            _create_login_log(db, "charlie", user.user_id, "9.9.9.9", "DisabledBrowser/1.0", "blocked", "account_disabled")

            log = db.query(LoginLog).filter(LoginLog.username == "charlie").first()
            assert log is not None
            assert log.status == "blocked"
            assert log.failure_reason == "account_disabled"
            assert log.user_id == user.user_id
        finally:
            db.close()


class TestIPExtraction:
    """IP 提取测试"""

    def test_x_forwarded_for_first_ip(self):
        from app.utils.request import extract_client_ip
        from fastapi import Request

        mock_request = MagicMock(spec=Request)
        mock_request.headers = {"x-forwarded-for": "1.2.3.4, 5.6.7.8"}
        mock_request.headers.get = mock_request.headers.get.__wrapped__
        # 直接 mock headers.get
        mock_request.headers = MagicMock()
        mock_request.headers.get = lambda key: {
            "x-forwarded-for": "1.2.3.4, 5.6.7.8"
        }.get(key)

        ip = extract_client_ip(mock_request)
        assert ip == "1.2.3.4"

    def test_x_real_ip_fallback(self):
        from app.utils.request import extract_client_ip
        from fastapi import Request

        mock_request = MagicMock(spec=Request)
        mock_request.headers = MagicMock()
        mock_request.headers.get = lambda key: {
            "x-real-ip": "7.7.7.7"
        }.get(key)

        ip = extract_client_ip(mock_request)
        assert ip == "7.7.7.7"

    def test_client_host_fallback(self):
        from app.utils.request import extract_client_ip
        from fastapi import Request

        mock_request = MagicMock(spec=Request)
        mock_request.headers = MagicMock()
        mock_request.headers.get = lambda key: None
        mock_request.client = MagicMock()
        mock_request.client.host = "192.168.1.1"

        ip = extract_client_ip(mock_request)
        assert ip == "192.168.1.1"

    def test_no_forwarded_headers(self):
        from app.utils.request import extract_client_ip
        from fastapi import Request

        mock_request = MagicMock(spec=Request)
        mock_request.headers = MagicMock()
        mock_request.headers.get = lambda key: None
        mock_request.client = None

        ip = extract_client_ip(mock_request)
        assert ip is None


class TestUserAgentTruncation:
    """User-Agent 截断到 500 字符"""

    def test_truncate_long_user_agent(self):
        from app.utils.request import extract_user_agent
        from fastapi import Request

        long_ua = "A" * 600
        mock_request = MagicMock(spec=Request)
        mock_request.headers = MagicMock()
        mock_request.headers.get = lambda key: long_ua if key == "user-agent" else None

        ua = extract_user_agent(mock_request)
        assert len(ua) == 500

    def test_short_user_agent_unchanged(self):
        from app.utils.request import extract_user_agent
        from fastapi import Request

        short_ua = "Mozilla/5.0"
        mock_request = MagicMock(spec=Request)
        mock_request.headers = MagicMock()
        mock_request.headers.get = lambda key: short_ua if key == "user-agent" else None

        ua = extract_user_agent(mock_request)
        assert ua == "Mozilla/5.0"


class TestLoginLogWriteFailure:
    """日志写入失败不阻塞登录响应"""

    def test_log_failure_does_not_block_login(self):
        # 注册一个真实用户
        db = TestingSessionLocal()
        try:
            _create_user(db, "dave", "dave@example.com", password="pwd123")
        finally:
            db.close()

        # 在 inner 边界 mock（构造 LoginLog 时抛异常），让真实的 _create_login_log 内部 try/except 捕获
        from app.models.login_log import LoginLog
        with patch.object(LoginLog, "__init__", side_effect=Exception("DB write error")):
            response = client.post(
                "/api/v1/auth/login",
                data={"username": "dave", "password": hash_password_sha256("pwd123")},
            )
            assert response.status_code == 200
            assert "access_token" in response.json()
            assert response.json()["token_type"] == "bearer"
