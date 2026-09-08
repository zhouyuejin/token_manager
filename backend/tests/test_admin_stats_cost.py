"""
测试 /admin/stats/usage 的 cost 计算。

覆盖矩阵：
  T1  价格配齐 + 用量存在 → cost > 0
  T2  UsageLog.model 匹配 provider_model 而非 model_id → cost > 0
  T3  价格全为 0 → cost = 0（合法，不算 bug）
  T4  UsageLog.model 完全对不上任何 ModelMapping → cost = 0（合法，不算 bug）

如果用户改了 admin.py 里的 cost 公式但忘了同步，T1/T2 会立刻失败。
"""
import os
import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine, text
from sqlalchemy.orm import sessionmaker

from app.main import app as fastapi_app
from app.core.database import Base, get_db
from app.core.security import hash_password_sha256
from app.models.user import User, UserRole, UserStatus
from app.models.provider import Provider, ProviderType, ProviderStatus
from app.models.model_mapping import ModelMapping, ModelMappingStatus
from app.models.usage_log import UsageLog

import app.models  # noqa: F401, E402

# ---- DB setup (mirrors test_api_key_admin_endpoints.py) ----
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


# ---- Helpers ----
def _truncate():
    db = TestingSessionLocal()
    try:
        for table in reversed(Base.metadata.sorted_tables):
            db.execute(text("SET FOREIGN_KEY_CHECKS=0"))
            db.execute(text(f"TRUNCATE TABLE {table.name}"))
            db.execute(text("SET FOREIGN_KEY_CHECKS=1"))
        db.commit()
    finally:
        db.close()


@pytest.fixture(autouse=True)
def _clean_db():
    _truncate()
    yield
    _truncate()


def _make_admin():
    db = TestingSessionLocal()
    try:
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
    finally:
        db.close()


def _make_provider(pid="prov_1"):
    db = TestingSessionLocal()
    try:
        p = Provider(
            provider_id=pid, name="P", type=ProviderType.openai,
            endpoint="https://x/", api_key="k", status=ProviderStatus.active,
        )
        db.add(p); db.commit()
    finally:
        db.close()


def _make_mapping(model_id, provider_model, in_price, out_price, provider_id="prov_1"):
    db = TestingSessionLocal()
    try:
        m = ModelMapping(
            model_id=model_id,
            provider_id=provider_id,
            provider_model=provider_model,
            display_name=model_id,
            status=ModelMappingStatus.active,
            price_per_1k_input=in_price,
            price_per_1k_output=out_price,
        )
        db.add(m); db.commit()
    finally:
        db.close()


def _make_usage(model, prompt_tokens, completion_tokens, today=True):
    """Insert a UsageLog. By default created_at = today so it falls in the default 7-day window."""
    from datetime import datetime
    db = TestingSessionLocal()
    try:
        u = UsageLog(
            log_id=f"log_{model}_{prompt_tokens}_{completion_tokens}",
            user_id="usr_admin",
            key_id="key_1",
            provider_id="prov_1",
            model=model,
            prompt_tokens=prompt_tokens,
            completion_tokens=completion_tokens,
            total_tokens=prompt_tokens + completion_tokens,
            latency_ms=100,
            status_code=200,
            created_at=datetime.now(),
        )
        db.add(u); db.commit()
    finally:
        db.close()


def _admin_token():
    h = hash_password_sha256("adminpass")
    r = client.post("/api/v1/auth/login", data={"username": "admin", "password": h})
    assert r.status_code == 200, r.text
    return r.json()["access_token"]


def _fetch_costs(model_id):
    """Hit the admin stats endpoint and pull by_model[].cost for the given model_id."""
    tok = _admin_token()
    r = client.get(
        "/api/v1/admin/stats/usage",
        headers={"Authorization": f"Bearer {tok}"},
    )
    assert r.status_code == 200, r.text
    rows = r.json()["by_model"]
    matches = [row["cost"] for row in rows if row["model"] == model_id]
    return matches[0] if matches else None


# ---- Tests ----

class TestAdminStatsCost:
    """回归测试：cost 必须按 ModelMapping 里的价格计算。"""

    def test_T1_priced_model_with_usage_yields_positive_cost(self):
        """model_id 匹配 + 价格齐全 + 有用量 → cost > 0。"""
        _make_admin()
        _make_provider()
        _make_mapping(model_id="gpt-4", provider_model="gpt-4",
                      in_price=0.01, out_price=0.03)
        # 1000 prompt + 500 completion:
        #   cost = 1000/1000 * 0.01 + 500/1000 * 0.03 = 0.01 + 0.015 = 0.025
        _make_usage("gpt-4", 1000, 500)
        cost = _fetch_costs("gpt-4")
        assert cost is not None, "by_model 里没找到 gpt-4 这一行"
        assert abs(cost - 0.025) < 1e-9, f"expected 0.025, got {cost}"

    def test_T2_match_via_provider_model(self):
        """UsageLog.model 等于 provider_model（不是 model_id）时也要算出来。"""
        _make_admin()
        _make_provider()
        # 内部 model_id = "openai-gpt-4"，上游 provider_model = "gpt-4"
        _make_mapping(model_id="openai-gpt-4", provider_model="gpt-4",
                      in_price=0.02, out_price=0.04)
        _make_usage("gpt-4", 2000, 1000)
        # 预期：2000/1000*0.02 + 1000/1000*0.04 = 0.04 + 0.04 = 0.08
        cost = _fetch_costs("gpt-4")
        assert cost is not None, "by_model 里没找到 gpt-4（说明 provider_model 匹配逻辑坏了）"
        assert abs(cost - 0.08) < 1e-9, f"expected 0.08, got {cost}"

    def test_T3_zero_prices_means_zero_cost(self):
        """价格全 0 → cost 必须 = 0（这是合法行为，不是 bug）。"""
        _make_admin()
        _make_provider()
        _make_mapping(model_id="m0", provider_model="m0",
                      in_price=0, out_price=0)
        _make_usage("m0", 5000, 5000)
        cost = _fetch_costs("m0")
        assert cost is not None
        assert cost == 0.0

    def test_T4_unmapped_model_yields_zero_cost(self):
        """UsageLog.model 不匹配任何 ModelMapping → cost = 0（合法行为）。"""
        _make_admin()
        _make_provider()
        _make_mapping(model_id="m0", provider_model="m0",
                      in_price=0.01, out_price=0.01)
        _make_usage("orphan-model", 9999, 9999)  # ← 不在 ModelMapping 里
        # orphan-model 仍会出现在 by_model 里，但 cost 必须 = 0
        cost = _fetch_costs("orphan-model")
        assert cost is not None, "orphan-model 应该出现在 by_model 里"
        assert cost == 0.0
