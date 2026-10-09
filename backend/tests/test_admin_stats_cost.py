"""管理员用量统计在当前 Model/ModelChannel 契约下的成本回归。"""
import os
from datetime import datetime

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine, text
from sqlalchemy.orm import sessionmaker

import app.models  # noqa: F401
from app.core.database import Base, get_db
from app.core.security import hash_password_sha256
from app.main import app as fastapi_app
from app.models.channel import Channel, ChannelType, ChannelStatus
from app.models.model import Model
from app.models.model_channel import ModelChannel
from app.models.usage_log import UsageLog
from app.models.user import User, UserRole, UserStatus


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


fastapi_app.dependency_overrides[get_db] = override_get_db
client = TestClient(fastapi_app)


@pytest.fixture(autouse=True)
def clean_db():
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


def _setup(model_id, usage_model, input_price, output_price, prompt=1000, completion=500, upstream=None):
    db = TestingSessionLocal()
    try:
        db.add(User(
            user_id="usr_admin", username="admin", email="admin@example.com",
            password=hash_password_sha256("adminpass"), role=UserRole.admin,
            status=UserStatus.active, model_group_ids="[]",
        ))
        model = Model(
            model_id=model_id, display_name=model_id,
            price_per_1k_input=input_price, price_per_1k_output=output_price,
        )
        db.add(model)
        if upstream:
            channel = Channel(
                channel_id="ch_1", name="P", type=ChannelType.openai,
                endpoint="https://x/", api_key="k", status=ChannelStatus.active,
            )
            db.add(channel)
            db.add(ModelChannel(model_id=model_id, channel_id="ch_1", upstream_model=upstream))
        db.add(UsageLog(
            log_id="log_1", user_id="usr_admin", key_id="key_1",
            channel_id="ch_1" if upstream else None, model=usage_model,
            prompt_tokens=prompt, completion_tokens=completion,
            total_tokens=prompt + completion, latency_ms=100, status_code=200,
            created_at=datetime.now(),
        ))
        db.commit()
    finally:
        db.close()


def _fetch_stats():
    response = client.post("/api/v1/auth/login", data={
        "username": "admin", "password": hash_password_sha256("adminpass"),
    })
    assert response.status_code == 200, response.text
    response = client.get(
        "/api/v1/admin/stats/usage",
        headers={"Authorization": f"Bearer {response.json()['access_token']}"},
    )
    assert response.status_code == 200, response.text
    return response.json()


def test_cost_uses_model_id_price_over_http():
    _setup("gpt-4", "gpt-4", 0.01, 0.03)

    stats = _fetch_stats()

    assert stats["by_model"][0]["cost"] == pytest.approx(0.025)


def test_cost_maps_upstream_model_to_model_id_over_http():
    _setup("openai-gpt-4", "gpt-4", 0.02, 0.04, prompt=2000, completion=1000, upstream="gpt-4")

    stats = _fetch_stats()

    assert stats["by_model"][0]["cost"] == pytest.approx(0.08)


def test_zero_price_is_a_valid_zero_cost():
    _setup("m0", "m0", 0, 0)

    assert _fetch_stats()["by_model"][0]["cost"] == 0


def test_unmapped_usage_model_has_zero_cost():
    _setup("m0", "orphan-model", 0.01, 0.01)

    stats = _fetch_stats()

    assert stats["by_model"][0]["model"] == "orphan-model"
    assert stats["by_model"][0]["cost"] == 0


def test_deleting_model_keeps_usage_history():
    _setup("gpt-4", "gpt-4", 0.01, 0.03)
    login = client.post("/api/v1/auth/login", data={
        "username": "admin", "password": hash_password_sha256("adminpass"),
    })
    headers = {"Authorization": f"Bearer {login.json()['access_token']}"}

    response = client.delete("/api/v1/admin/models/gpt-4", headers=headers)
    assert response.status_code == 200, response.text
    db = TestingSessionLocal()
    try:
        assert db.query(UsageLog).filter_by(model="gpt-4").count() == 1
    finally:
        db.close()


def test_channel_usage_exposes_id_and_saved_cost():
    _setup('m', 'm', 1, 1, upstream='upstream-m')
    db = TestingSessionLocal()
    try:
        row = db.query(UsageLog).one()
        row.cost_usd = 0.25
        db.commit()
    finally:
        db.close()
    channel = _fetch_stats()['by_provider'][0]
    assert channel['channel_id'] == 'ch_1'
    assert channel['cost'] == 0.25
