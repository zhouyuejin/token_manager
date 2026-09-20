import csv
import io
from datetime import datetime
from decimal import Decimal

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from sqlalchemy import BigInteger, create_engine
from sqlalchemy.ext.compiler import compiles
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

import app.models  # noqa: F401
from app.api.v1 import admin
from app.core.database import Base, get_db
from app.dependencies import require_admin
from app.models.channel import Channel
from app.models.organization import Department
from app.models.project import Project
from app.models.usage_log import UsageLog
from app.models.user import User, UserRole


@compiles(BigInteger, "sqlite")
def sqlite_bigint(element, compiler, **kw):
    return "INTEGER"


@pytest.fixture
def ctx():
    engine = create_engine("sqlite://", connect_args={"check_same_thread": False}, poolclass=StaticPool)
    Base.metadata.create_all(engine)
    db = sessionmaker(bind=engine)()
    administrator = User(
        user_id="admin", username="admin", email="admin@test", password="hash", role=UserRole.admin
    )
    alice = User(user_id="alice", username="Alice", email="alice@test", password="hash")
    department = Department(dept_id="dept-1", name="研发部")
    project = Project(project_id="project-1", dept_id="dept-1", name="平台")
    channel = Channel(channel_id="channel-1", name="主渠道", api_key="secret")
    db.add_all([administrator, alice, department, project, channel])
    match = dict(
        user_id="alice", key_id="key-1", channel_id="channel-1", model="gpt-test",
        project_id="project-1", department_id="dept-1", prompt_tokens=70,
        completion_tokens=30, total_tokens=100, cost_usd=Decimal("0.25000000"),
        latency_ms=20, status_code=200, created_at=datetime(2026, 9, 20, 8, 0),
    )
    db.add_all([
        UsageLog(log_id="match", **match),
        UsageLog(log_id="other-department", **{**match, "department_id": "dept-2"}),
        UsageLog(log_id="other-project", **{**match, "project_id": "project-2"}),
        UsageLog(log_id="other-user", **{**match, "user_id": "bob"}),
        UsageLog(log_id="other-model", **{**match, "model": "other-model"}),
        UsageLog(log_id="other-channel", **{**match, "channel_id": "channel-2"}),
        UsageLog(log_id="other-date", **{**match, "created_at": datetime(2026, 9, 19, 8, 0)}),
        UsageLog(
            log_id="other", user_id="admin", key_id="key-2", channel_id=None,
            model="other", prompt_tokens=10, completion_tokens=0, total_tokens=10,
            cost_usd=Decimal("0.01000000"), latency_ms=30, status_code=500,
            created_at=datetime(2026, 9, 20, 9, 0),
        ),
    ])
    db.commit()

    api = FastAPI()
    api.include_router(admin.router, prefix="/admin")
    api.dependency_overrides[get_db] = lambda: db
    api.dependency_overrides[require_admin] = lambda: administrator
    with TestClient(api) as client:
        yield client
    db.close()
    engine.dispose()


def test_report_export_reuses_all_stats_filters_and_totals(ctx):
    params = {
        "start_date": "2026-09-20", "end_date": "2026-09-20",
        "department_id": "dept-1", "project_id": "project-1", "user_id": "alice",
        "model": "gpt-test", "channel_id": "channel-1",
    }
    stats = ctx.get("/admin/stats/usage", params=params)
    assert stats.status_code == 200, stats.text
    assert stats.json()["total_tokens"] == 100
    assert stats.json()["total_cost"] == 0.25

    exported = ctx.get("/admin/stats/usage/export", params=params)
    assert exported.status_code == 200, exported.text
    assert exported.headers["content-type"].startswith("text/csv")
    assert "attachment;" in exported.headers["content-disposition"]
    rows = list(csv.reader(io.StringIO(exported.content.decode("utf-8-sig"))))
    assert rows[0] == ["时间", "部门", "项目", "用户", "API Key", "模型", "渠道", "输入Token", "输出Token", "总Token", "成本(USD)", "状态码"]
    assert rows[1][1:7] == ["研发部", "平台", "Alice", "key-1", "gpt-test", "主渠道"]
    assert rows[1][9:12] == ["100", "0.25000000", "200"]
    assert rows[-1] == ["汇总", "", "", "", "", "", "", "70", "30", "100", "0.25000000", "1 次请求"]
