"""昵称维护、用户展示数据和旧账号兼容。"""
import importlib.util
import csv
import io
from datetime import datetime
from pathlib import Path

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from sqlalchemy import BigInteger, create_engine, text, inspect
from sqlalchemy.ext.compiler import compiles
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

import app.models
from app.api.v1 import admin, users, projects, approvals, auth
from app.core.database import Base, get_db
from app.dependencies import get_current_user, require_admin
from app.models.user import User, UserRole


@compiles(BigInteger, "sqlite")
def sqlite_bigint(element, compiler, **kw):
    return "INTEGER"


@pytest.fixture
def ctx():
    engine = create_engine("sqlite://", connect_args={"check_same_thread": False}, poolclass=StaticPool)
    Base.metadata.create_all(engine)
    db = sessionmaker(bind=engine)()
    owner = User(user_id="owner", username="account", email="owner@example.com", password="hash")
    administrator = User(user_id="admin", username="admin", email="admin@example.com", password="hash", role=UserRole.admin)
    db.add_all([owner, administrator])
    db.commit()
    app = FastAPI()
    app.include_router(users.router, prefix="/users")
    app.include_router(admin.router, prefix="/admin")
    app.include_router(projects.router, prefix="/projects")
    app.include_router(approvals.router, prefix="/approvals")
    app.include_router(auth.router, prefix="/auth")
    app.dependency_overrides[get_db] = lambda: db
    app.dependency_overrides[get_current_user] = lambda: owner
    app.dependency_overrides[require_admin] = lambda: administrator
    with TestClient(app) as client:
        yield db, client, owner
    db.close()
    engine.dispose()


def test_personal_nickname_save_clear_and_account_unchanged(ctx):
    db, client, owner = ctx
    assert client.get("/users/me").json()["nickname"] is None
    response = client.put("/users/me/profile", json={"nickname": "  小周  ", "username": "changed", "role": "admin"})
    assert response.status_code == 200, response.text
    assert client.get("/users/me").json()["nickname"] == "小周"
    db.refresh(owner)
    assert owner.username == "account" and owner.role == UserRole.user
    assert client.put("/users/me/profile", json={"nickname": " "}).status_code == 200
    assert client.get("/users/me").json()["nickname"] is None
    assert client.put("/users/me/profile", json={"nickname": None}).status_code == 200
    assert client.put("/users/me/profile", json={"nickname": "周" * 51}).status_code == 422
    assert client.put("/users/me/profile", json={}).status_code == 422


def test_admin_nickname_create_search_update_and_clear(ctx):
    db, client, owner = ctx
    response = client.post("/admin/users", json={
        "username": "new-account", "nickname": "  新昵称  ",
        "email": "new@example.com", "password": "a" * 64,
    })
    assert response.status_code == 200, response.text
    user = response.json()
    assert user["nickname"] == "新昵称"
    assert client.get("/admin/users", params={"keyword": "新昵称"}).json()["total"] == 1
    assert client.put(f"/admin/users/{user['user_id']}", json={"nickname": "改昵称"}).status_code == 200
    assert client.get(f"/admin/users/{user['user_id']}").json()["nickname"] == "改昵称"
    assert client.put(f"/admin/users/{user['user_id']}", json={"email": "updated@example.com"}).status_code == 200
    assert client.get(f"/admin/users/{user['user_id']}").json()["nickname"] == "改昵称"
    assert client.put(f"/admin/users/{user['user_id']}", json={"nickname": ""}).status_code == 200
    assert client.get(f"/admin/users/{user['user_id']}").json()["nickname"] is None
    assert client.put(f"/admin/users/{owner.user_id}", json={"nickname": "周" * 51}).status_code == 422


def test_project_members_include_nickname(ctx):
    db, client, owner = ctx
    client.put("/users/me/profile", json={"nickname": "项目成员"})
    department = client.post("/projects/admin/departments", json={"name": "研发部"}).json()
    project = client.post("/projects/admin", json={"name": "平台", "dept_id": department["dept_id"]}).json()
    url = f"/projects/admin/{project['project_id']}/users"
    assert client.put(url, json={"user_ids": [owner.user_id]}).status_code == 200
    assert client.get(url).json()["items"] == [{"user_id": owner.user_id, "username": "account", "nickname": "项目成员"}]


def test_department_owner_display_prefers_nickname_and_falls_back(ctx):
    db, client, owner = ctx
    department = client.post("/projects/admin/departments", json={
        "name": "研发部", "owner_user_id": owner.user_id,
    }).json()
    client.post("/projects/admin/departments", json={"name": "未分配部门"})

    def departments():
        response = client.get("/projects/admin/departments")
        assert response.status_code == 200, response.text
        return {row["dept_id"]: row for row in response.json()["items"]}

    assert departments()[department["dept_id"]]["owner_name"] == "account"
    owner.nickname = "部门负责人"
    db.commit()
    rows = departments()
    assert rows[department["dept_id"]]["owner_name"] == "部门负责人"
    assert rows[department["dept_id"]]["owner_user_id"] == owner.user_id
    assert next(row for row in rows.values() if row["name"] == "未分配部门")["owner_name"] is None


def test_approval_requesters_include_nickname_and_keep_visibility(ctx):
    from app.models.approval import ApprovalRequest

    db, client, owner = ctx
    owner.nickname = "申请人昵称"
    db.add_all([
        ApprovalRequest(request_id="visible", request_type="quota", requester_user_id=owner.user_id,
                        approver_user_id=owner.user_id, payload={}, reason="test"),
        ApprovalRequest(request_id="hidden", request_type="quota", requester_user_id="admin",
                        approver_user_id="admin", payload={}, reason="test"),
    ])
    db.commit()
    response = client.get("/approvals/review/requesters")
    assert response.status_code == 200, response.text
    assert response.json() == [{"user_id": owner.user_id, "username": "account", "nickname": "申请人昵称"}]


def test_nickname_does_not_replace_login_account(ctx):
    db, client, owner = ctx
    owner.nickname = "登录展示"
    db.commit()
    assert client.post("/auth/login", json={"username": "登录展示", "password": "hash"}).status_code == 401
    response = client.post("/auth/login", json={"username": "account", "password": "hash"})
    assert response.status_code == 200, response.text
    assert response.json()["access_token"]


def test_usage_stats_and_export_prefer_nickname_without_losing_username(ctx):
    from app.models.usage_log import UsageLog

    db, client, owner = ctx
    owner.nickname = "统计昵称"
    db.add(UsageLog(
        log_id="nickname-usage", user_id=owner.user_id, key_id="key", model="test-model",
        prompt_tokens=70, completion_tokens=30, total_tokens=100, cost_usd=0,
        latency_ms=20, status_code=200, created_at=datetime(2026, 10, 8, 8),
    ))
    db.commit()
    params = {"start_date": "2026-10-08", "end_date": "2026-10-08"}
    response = client.get("/admin/stats/usage", params=params)
    assert response.status_code == 200, response.text
    assert response.json()["by_user"] == [{
        "user_id": owner.user_id, "username": "account", "nickname": "统计昵称",
        "tokens": 100, "requests": 1,
    }]
    response = client.get("/admin/stats/usage/export", params=params)
    assert response.status_code == 200, response.text
    rows = list(csv.reader(io.StringIO(response.text.lstrip("\ufeff"))))
    assert rows[1][3] == "统计昵称"
    owner.nickname = None
    db.commit()
    response = client.get("/admin/stats/usage/export", params=params)
    rows = list(csv.reader(io.StringIO(response.text.lstrip("\ufeff"))))
    assert rows[1][3] == "account"


def test_nickname_migration_preserves_existing_accounts():
    from alembic.migration import MigrationContext
    from alembic.operations import Operations

    path = Path(__file__).parents[1] / "alembic/versions/20261008_1000_user_nickname.py"
    spec = importlib.util.spec_from_file_location("nickname_migration", path)
    migration = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(migration)
    engine = create_engine("sqlite://")
    with engine.begin() as connection:
        connection.execute(text("CREATE TABLE users (user_id VARCHAR(32) PRIMARY KEY, username VARCHAR(50))"))
        connection.execute(text("INSERT INTO users VALUES ('old-user', 'old-account')"))
        migration.op = Operations(MigrationContext.configure(connection))
        migration.upgrade()
        assert connection.execute(text("SELECT username, nickname FROM users")).one() == ("old-account", None)
        migration.downgrade()
        assert "nickname" not in {column["name"] for column in inspect(connection).get_columns("users")}
        assert connection.execute(text("SELECT username FROM users")).scalar() == "old-account"
    engine.dispose()
