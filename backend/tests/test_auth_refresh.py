"""refresh token 端点测试"""
import pytest
from datetime import datetime, timedelta
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool
from sqlalchemy import event
from sqlalchemy.orm import Session

from app.main import app
from app.core.database import Base, get_db
from app.core.config import settings
from app.core.security import get_password_hash, generate_user_id, hash_token
from app.models.user import User, UserRole, UserStatus
from app.models.refresh_token import RefreshToken
from app.api.v1 import auth as auth_module

# 内存 SQLite 测试库
TEST_DATABASE_URL = "sqlite:///:memory:"
engine = create_engine(
    TEST_DATABASE_URL,
    connect_args={"check_same_thread": False},
    poolclass=StaticPool,  # TestClient 走独立连接，需要 StaticPool 让 :memory: 共享
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


_id_counters: dict[str, int] = {}


# 受 BigInteger PK + SQLite 影响、需要补 id 的模型
from app.models.user import User as _User
from app.models.refresh_token import RefreshToken as _RT

_id_counters: dict[str, int] = {}


def _bind_pk_assigner(model_cls):
    @event.listens_for(model_cls, "before_insert", propagate=True)
    def _assign_pk(mapper, connection, target):
        # 主键名为 id 且未设值时，递增分配
        if getattr(target, "id", None) is not None:
            return
        table = target.__tablename__
        _id_counters[table] = _id_counters.get(table, 0) + 1
        target.id = _id_counters[table]

_bind_pk_assigner(_User)
_bind_pk_assigner(_RT)


@pytest.fixture(autouse=True)
def setup_db():
    Base.metadata.create_all(bind=engine)
    _id_counters.clear()
    yield
    Base.metadata.drop_all(bind=engine)
    _id_counters.clear()


@pytest.fixture(autouse=True)
def disable_login_log(monkeypatch):
    """
    login 端点会在 success 时写 LoginLog。SQLite in-memory 模式下 BigInteger
    PK 不会 autoincrement，写入会失败。但 LoginLog 不是本次被测对象，
    直接让它 no-op。
    """
    monkeypatch.setattr(auth_module, "_create_login_log", lambda *a, **kw: None)


@pytest.fixture
def user_row():
    db = TestingSessionLocal()
    u = User(
        user_id=generate_user_id(),
        username="alice",
        email="alice@example.com",
        password=get_password_hash("S3cretpwd"),
        role=UserRole.user,
        status=UserStatus.active,
    )
    db.add(u)
    db.commit()
    db.refresh(u)
    db.close()
    return u


def _login(username="alice", password="S3cretpwd") -> dict:
    res = client.post("/api/v1/auth/login",
        data={"username": username, "password": password},
        headers={"Content-Type": "application/x-www-form-urlencoded"})
    assert res.status_code == 200, res.text
    body = res.json()
    # 新版 Token 必须含 refresh_token + expires_in
    assert "refresh_token" in body, body
    assert "expires_in" in body, body
    return body


# ===== /auth/login =====
class TestLoginWithRefresh:
    def test_login_returns_refresh_token(self, user_row):
        body = _login()
        assert body["token_type"] == "bearer"
        assert len(body["refresh_token"]) > 40
        assert body["expires_in"] == settings.ACCESS_TOKEN_EXPIRE_MINUTES * 60

    def test_login_persists_refresh_token_row(self, user_row):
        body = _login()
        db = TestingSessionLocal()
        rows = db.query(RefreshToken).filter(RefreshToken.user_id == user_row.user_id).all()
        assert len(rows) == 1
        assert rows[0].revoked == False  # noqa: E712
        assert rows[0].token_hash == hash_token(body["refresh_token"])
        db.close()


# ===== /auth/refresh =====
class TestRefresh:
    def test_refresh_success_returns_new_pair(self, user_row):
        first = _login()
        res = client.post("/api/v1/auth/refresh", json={"refresh_token": first["refresh_token"]})
        assert res.status_code == 200, res.text
        body = res.json()
        assert body["access_token"] != first["access_token"], "应发新 access_token"
        assert body["refresh_token"] != first["refresh_token"], "rotation: 应发新 refresh_token"

    def test_refresh_revokes_old_token(self, user_row):
        first = _login()
        client.post("/api/v1/auth/refresh", json={"refresh_token": first["refresh_token"]})
        # 用旧 refresh_token 再 refresh → 应 401
        res = client.post("/api/v1/auth/refresh", json={"refresh_token": first["refresh_token"]})
        assert res.status_code == 401

    def test_refresh_unknown_token_rejected(self, user_row):
        res = client.post("/api/v1/auth/refresh", json={"refresh_token": "totally-bogus"})
        assert res.status_code == 401

    def test_refresh_expired_token_rejected(self, user_row):
        first = _login()
        # 手动把 DB 里那条 token 设为过期
        db = TestingSessionLocal()
        row = db.query(RefreshToken).filter(RefreshToken.user_id == user_row.user_id).first()
        row.expires_at = datetime.utcnow() - timedelta(days=1)
        db.commit(); db.close()

        res = client.post("/api/v1/auth/refresh", json={"refresh_token": first["refresh_token"]})
        assert res.status_code == 401

    def test_refresh_with_disabled_user_rejected(self, user_row):
        first = _login()
        db = TestingSessionLocal()
        u = db.query(User).filter(User.user_id == user_row.user_id).first()
        u.status = UserStatus.disabled
        db.commit(); db.close()

        res = client.post("/api/v1/auth/refresh", json={"refresh_token": first["refresh_token"]})
        assert res.status_code == 401


# ===== /auth/logout =====
class TestLogout:
    def test_logout_revokes_refresh_token(self, user_row):
        first = _login()
        res = client.post("/api/v1/auth/logout", json={"refresh_token": first["refresh_token"]})
        assert res.status_code == 204

        # 登出后旧 refresh_token 失效
        res2 = client.post("/api/v1/auth/refresh", json={"refresh_token": first["refresh_token"]})
        assert res2.status_code == 401

    def test_logout_without_body_ok(self, user_row):
        _login()
        res = client.post("/api/v1/auth/logout", json={})
        assert res.status_code == 204
