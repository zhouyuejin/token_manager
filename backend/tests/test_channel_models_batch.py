"""
测试渠道批量绑定模型接口（修复"获取模型"批量导入 N 次调用 bug）。

复现：在模型管理页面获取 N 个上游 model → bindChannelToModel 调用 N 次。
期望：新增批量接口 1 次调用完成全部绑定。
"""
import os
import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine, text
from sqlalchemy.orm import sessionmaker

import app.models  # noqa: F401, E402
from app.main import app as fastapi_app
from app.core.database import Base, get_db
from app.models.user import User, UserRole, UserStatus
from app.models.channel import Channel, ChannelType, ChannelStatus
from app.models.model import Model, ModelStatus, PriceType
from app.models.model_channel import ModelChannel
from app.core.security import hash_password_sha256

TEST_DATABASE_URL = os.environ.get(
    "TEST_DATABASE_URL",
    "mysql+pymysql://token_user:token_password@mysql:3306/token_db_test?charset=utf8mb4",
)
engine = create_engine(TEST_DATABASE_URL, pool_pre_ping=True)
Base.metadata.create_all(bind=engine)
TestingSessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)


def _override_get_db():
    db = TestingSessionLocal()
    try:
        yield db
    finally:
        db.close()


client = TestClient(fastapi_app)


@pytest.fixture(autouse=True)
def setup_db():
    """每个测试用 TRUNCATE 清理（MySQL）。"""
    _prev = fastapi_app.dependency_overrides.get(get_db)
    fastapi_app.dependency_overrides[get_db] = _override_get_db

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

    if _prev is not None:
        fastapi_app.dependency_overrides[get_db] = _prev
    else:
        fastapi_app.dependency_overrides.pop(get_db, None)


# ========== Fixtures ==========

def _create_admin(db):
    admin = User(
        user_id="usr_admin",
        username="admin",
        email="admin@example.com",
        password=hash_password_sha256("adminpass"),
        role=UserRole.admin,
        status=UserStatus.active,
        model_group_ids="[]",
    )
    db.add(admin)
    db.commit()
    db.refresh(admin)
    return admin


def _admin_token():
    response = client.post(
        "/api/v1/auth/login",
        data={"username": "admin", "password": hash_password_sha256("adminpass")},
    )
    assert response.status_code == 200, f"Login failed: {response.json()}"
    return response.json()["access_token"]


def _create_channel(db, channel_id="ch_001", name="测试渠道"):
    ch = Channel(
        channel_id=channel_id,
        name=name,
        type=ChannelType.openai,
        endpoint="https://example.com",
        api_key="test-key",
        priority=0,
        timeout=30,
        status=ChannelStatus.active,
    )
    db.add(ch)
    db.commit()
    db.refresh(ch)
    return ch


def _create_model(db, model_id="m1", display_name="测试模型"):
    m = Model(
        model_id=model_id,
        display_name=display_name,
        price_type=PriceType.token,
        price_per_1k_input=0,
        price_per_1k_output=0,
        price_per_request=0,
        status=ModelStatus.active,
    )
    db.add(m)
    db.commit()
    db.refresh(m)
    return m


# ========== Tests ==========

class TestBatchChannelModels:
    """测试渠道批量绑定模型接口"""

    def test_batch_bind_all_new_models(self):
        """5 个新 model → 1 次 HTTP 请求全部绑定成功"""
        db = TestingSessionLocal()
        try:
            _create_admin(db)
            _create_channel(db, "ch_001")
            for i in range(5):
                _create_model(db, f"m_{i}")

            token = _admin_token()
            headers = {"Authorization": f"Bearer {token}"}
            payload = [
                {
                    "model_id": f"m_{i}",
                    "upstream_model": f"upstream_{i}",
                    "priority": 0,
                    "weight": 100,
                    "enabled": True,
                }
                for i in range(5)
            ]
            response = client.post(
                "/api/v1/admin/channels/ch_001/models/batch",
                json=payload,
                headers=headers,
            )
            assert response.status_code == 200, response.text
            data = response.json()
            assert sorted(data["added"]) == [f"m_{i}" for i in range(5)]
            assert data["skipped"] == []
            assert data["errors"] == []

            # 用独立 session 校验落库，避免 testing session 的事务隔离问题
            db.commit()
            db.close()
            check_db = TestingSessionLocal()
            try:
                count = check_db.query(ModelChannel).filter(ModelChannel.channel_id == "ch_001").count()
                assert count == 5
            finally:
                check_db.close()
        finally:
            if db.is_active:
                db.close()

    def test_batch_bind_skips_already_bound(self):
        """重复绑定同一 model → 加入 skipped，不报错"""
        db = TestingSessionLocal()
        try:
            _create_admin(db)
            _create_channel(db, "ch_001")
            _create_model(db, "m_0")
            _create_model(db, "m_1")

            token = _admin_token()
            headers = {"Authorization": f"Bearer {token}"}

            # 先用单条接口绑 m_0
            r0 = client.post(
                "/api/v1/admin/channels/ch_001/models",
                json={"model_id": "m_0", "upstream_model": "m_0",
                      "priority": 0, "weight": 100, "enabled": True},
                headers=headers,
            )
            assert r0.status_code == 200, r0.text

            # 批量提交 [m_0, m_1]
            response = client.post(
                "/api/v1/admin/channels/ch_001/models/batch",
                json=[
                    {"model_id": "m_0", "upstream_model": "m_0",
                     "priority": 0, "weight": 100, "enabled": True},
                    {"model_id": "m_1", "upstream_model": "m_1",
                     "priority": 0, "weight": 100, "enabled": True},
                ],
                headers=headers,
            )
            assert response.status_code == 200, response.text
            data = response.json()
            assert data["added"] == ["m_1"]
            assert data["skipped"] == ["m_0"]
            assert data["errors"] == []
        finally:
            db.close()

    def test_batch_bind_reports_missing_model(self):
        """不存在的 model_id → 加入 errors，不影响其他 model 绑定"""
        db = TestingSessionLocal()
        try:
            _create_admin(db)
            _create_channel(db, "ch_001")
            _create_model(db, "m_real")

            token = _admin_token()
            headers = {"Authorization": f"Bearer {token}"}
            response = client.post(
                "/api/v1/admin/channels/ch_001/models/batch",
                json=[
                    {"model_id": "m_real", "upstream_model": "m_real",
                     "priority": 0, "weight": 100, "enabled": True},
                    {"model_id": "m_missing", "upstream_model": "m_missing",
                     "priority": 0, "weight": 100, "enabled": True},
                ],
                headers=headers,
            )
            assert response.status_code == 200, response.text
            data = response.json()
            assert data["added"] == ["m_real"]
            assert data["skipped"] == []
            assert len(data["errors"]) == 1
            assert "m_missing" in data["errors"][0]
        finally:
            db.close()

    def test_batch_bind_channel_not_found(self):
        """channel_id 不存在 → 404"""
        db = TestingSessionLocal()
        try:
            _create_admin(db)
            token = _admin_token()
            headers = {"Authorization": f"Bearer {token}"}
            response = client.post(
                "/api/v1/admin/channels/ch_nonexistent/models/batch",
                json=[{"model_id": "m_x", "upstream_model": "m_x",
                       "priority": 0, "weight": 100, "enabled": True}],
                headers=headers,
            )
            assert response.status_code == 404
        finally:
            db.close()

    def test_batch_bind_empty_list(self):
        """空列表 → 200，返回空结果（不做任何操作）"""
        db = TestingSessionLocal()
        try:
            _create_admin(db)
            _create_channel(db, "ch_001")

            token = _admin_token()
            headers = {"Authorization": f"Bearer {token}"}
            response = client.post(
                "/api/v1/admin/channels/ch_001/models/batch",
                json=[],
                headers=headers,
            )
            assert response.status_code == 200, response.text
            data = response.json()
            assert data["added"] == []
            assert data["skipped"] == []
            assert data["errors"] == []
        finally:
            db.close()
