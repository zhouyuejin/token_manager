import pytest
import asyncio
from fastapi import HTTPException
from starlette.requests import Request

from app.api.v1.auth import _oidc_user, login
from app.api.v1.admin import _apply_role_transition
from app.api.v1.projects import check_department_access
from app.dependencies import require_admin
from app.models.organization import Department
from app.models.role_permission import RolePermission
from app.models.user import User, UserRole, UserStatus
from app.schemas.admin import AdminUserCreate
from app.api.v1.admin import create_user


def make_request(method="GET", path="/api/v1/admin/users"):
    return Request({
        "type": "http", "method": method, "path": path, "headers": [],
        "query_string": b"", "server": ("test", 80), "scheme": "http",
    })


def make_user(role):
    return User(
        user_id=f"usr_{role.value}", username=role.value, email=f"{role.value}@example.com",
        password="x", role=role, status=UserStatus.active,
    )


def test_oidc_first_login_creates_user_and_reuses_subject(db, monkeypatch):
    from app.core.config import settings

    monkeypatch.setattr(settings, "OIDC_ISSUER_URL", "https://id.example.com")
    claims = {
        "sub": "subject-1", "email": "new@example.com", "email_verified": True,
        "preferred_username": "new-user",
    }
    user = _oidc_user(db, claims)
    again = _oidc_user(db, claims)

    assert user.user_id == again.user_id
    assert user.username == "new-user"
    assert user.role == UserRole.user
    assert user.oidc_subject == "https://id.example.com|subject-1"


def test_oidc_rejects_unverified_email(db, monkeypatch):
    from app.core.config import settings

    monkeypatch.setattr(settings, "OIDC_ISSUER_URL", "https://id.example.com")
    with pytest.raises(HTTPException) as exc:
        _oidc_user(db, {"sub": "subject-2", "email": "unverified@example.com", "email_verified": False})
    assert exc.value.status_code == 403


def test_password_login_can_be_disabled(db, monkeypatch):
    from app.core.config import settings

    monkeypatch.setattr(settings, "PASSWORD_LOGIN_ENABLED", False)
    with pytest.raises(HTTPException) as exc:
        asyncio.run(login(make_request("POST", "/api/v1/auth/login"), db))
    assert exc.value.status_code == 403


def test_auditor_can_read_but_cannot_write_admin_routes(db):
    db.add(RolePermission(role="auditor", permission="admin:read"))
    db.commit()
    auditor = make_user(UserRole.auditor)

    assert require_admin(make_request(), auditor, db) is auditor
    with pytest.raises(HTTPException) as exc:
        require_admin(make_request("PUT"), auditor, db)
    assert exc.value.status_code == 403


def test_non_admin_role_change_preserves_user_quota():
    user = make_user(UserRole.user)
    user.quota = 2500
    user.model_group_ids = '["group-1"]'
    changed = {}

    assert _apply_role_transition(user, "auditor", changed)
    assert user.role == UserRole.auditor
    assert user.quota == 2500
    assert user.model_group_ids == '["group-1"]'


def test_admin_can_create_user_with_new_role(db):
    password = "a" * 64
    result = asyncio.run(create_user(
        AdminUserCreate(username="auditor1", email="audit@example.com", password=password,
                        role="auditor", quota=0),
        db=db, admin=make_user(UserRole.admin),
    ))
    user = db.query(User).filter(User.username == "auditor1").one()
    assert result.role == "auditor"
    assert user.role == UserRole.auditor
    assert user.password == password


def test_department_admin_can_only_manage_owned_department(db):
    db.add(RolePermission(role="department_admin", permission="department:write"))
    db.add(Department(dept_id="dept_owned", name="Own", owner_user_id="usr_department_admin", status="active"))
    db.add(Department(dept_id="dept_other", name="Other", owner_user_id="someone-else", status="active"))
    db.commit()
    admin = make_user(UserRole.department_admin)

    assert require_admin(make_request("POST", "/api/v1/projects/admin"), admin, db) is admin
    check_department_access(db, admin, "dept_owned")
    with pytest.raises(HTTPException) as exc:
        check_department_access(db, admin, "dept_other")
    assert exc.value.status_code == 404
