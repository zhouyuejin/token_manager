import asyncio
import json
from datetime import datetime, timedelta

import pytest
from fastapi import HTTPException
from pydantic import ValidationError
from starlette.requests import Request

from app.api.v1.auth import login
from app.api.v1.admin import reset_user_password
from app.core.security import hash_password_sha256, verify_password
from app.dependencies import require_admin
from app.models.operation_log import OperationLog
from app.models.refresh_token import RefreshToken
from app.models.user import User, UserRole, UserStatus
from app.schemas.admin import AdminPasswordReset


def make_request(method="POST", path="/api/v1/admin/users/usr_target/reset-password"):
    return Request({
        "type": "http", "method": method, "path": path, "headers": [],
        "query_string": b"", "server": ("test", 80), "scheme": "http",
    })


def make_user(user_id, role, password):
    return User(
        user_id=user_id, username=user_id, email=f"{user_id}@example.com",
        password=password, role=role, status=UserStatus.active,
    )


def make_login_request(username, password):
    body = json.dumps({"username": username, "password": password}).encode()

    async def receive():
        return {"type": "http.request", "body": body, "more_body": False}

    return Request({
        "type": "http", "method": "POST", "path": "/api/v1/auth/login",
        "headers": [(b"content-type", b"application/json")],
        "query_string": b"", "server": ("test", 80), "scheme": "http",
    }, receive)


def test_admin_password_reset_updates_password_revokes_refresh_and_audits(db, monkeypatch):
    old_password = hash_password_sha256("old-password")
    new_password = hash_password_sha256("new-password")
    admin = make_user("usr_admin", UserRole.admin, "admin-password")
    target = make_user("usr_target", UserRole.user, old_password)
    db.add_all([admin, target, RefreshToken(
        token_id="refresh-1", user_id=target.user_id, token_hash="a" * 64,
        expires_at=datetime.utcnow() + timedelta(days=1),
    )])
    db.commit()

    result = asyncio.run(reset_user_password(
        user_id=target.user_id, data=AdminPasswordReset(new_password=new_password),
        request=make_request(), db=db, admin=admin,
    ))

    db.refresh(target)
    assert result["message"]
    assert not verify_password(old_password, target.password)
    assert verify_password(new_password, target.password)
    assert db.query(RefreshToken).filter_by(user_id=target.user_id).count() == 0

    from app.api.v1 import auth as auth_module
    monkeypatch.setattr(auth_module, "_create_login_log", lambda *args, **kwargs: None)
    with pytest.raises(HTTPException) as rejected:
        asyncio.run(login(make_login_request(target.username, old_password), db))
    assert rejected.value.status_code == 401
    assert asyncio.run(login(make_login_request(target.username, new_password), db)).access_token

    log = db.query(OperationLog).filter_by(action="reset_password", target_id=target.user_id).one()
    assert log.target_type == "user"
    detail = json.loads(log.detail)
    assert detail == {"username": target.username}
    assert old_password not in log.detail and new_password not in log.detail


def test_admin_password_reset_rejects_missing_user(db):
    with pytest.raises(HTTPException) as exc:
        asyncio.run(reset_user_password(
            user_id="missing", data=AdminPasswordReset(new_password="a" * 64),
            request=make_request(), db=db,
            admin=make_user("usr_admin", UserRole.admin, "password"),
        ))
    assert exc.value.status_code == 404
    assert exc.value.detail == "用户不存在"


def test_admin_password_reset_requires_admin_write_permission(db):
    from app.models.role_permission import RolePermission

    auditor = make_user("usr_auditor", UserRole.auditor, "password")
    db.add(RolePermission(role="auditor", permission="admin:read"))
    db.commit()

    with pytest.raises(HTTPException) as exc:
        require_admin(make_request(), auditor, db)
    assert exc.value.status_code == 403


def test_admin_password_reset_requires_sha256_hex():
    for invalid in ("short", "A" * 64, "g" * 64):
        with pytest.raises(ValidationError):
            AdminPasswordReset(new_password=invalid)
