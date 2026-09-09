"""
测试 admin.py 角色感知逻辑：
- create_user 收到 role='admin' 强制 quota=-1, model_group_ids='[]'
- update_user 的 role transition 自动副作用（promote / demote）
- update_user 对 admin 内部属性修改仍 400（保留旧行为，但允许 transition 通过）
- adjust_user_quota 对 admin 直接 400

策略：
- _apply_role_transition 用真实 User 对象（无 DB）
- 端点函数用 mocked db + asyncio.run 调用
"""
import asyncio
import pytest
from unittest.mock import MagicMock, AsyncMock

import app.models  # noqa: F401, E402
from app.models.user import User, UserRole, UserStatus
from app.schemas.admin import AdminUserUpdate, AdminUserCreate, QuotaAdjustRequest
from app.api.v1.admin import _apply_role_transition

def _run_async(coro):
    """Run an async coroutine without closing the default event loop (so subsequent
    tests using asyncio.get_event_loop() still work)."""
    loop = asyncio.new_event_loop()
    try:
        return loop.run_until_complete(coro)
    finally:
        loop.close()


def _make_user(role: UserRole, quota: int = 0, quota_used: int = 0,
               model_group_ids: str = "[]") -> User:
    return User(
        user_id="u1",
        username="x",
        email="x@x.com",
        password="h",
        role=role,
        status=UserStatus.active,
        quota=quota,
        quota_used=quota_used,
        model_group_ids=model_group_ids,
    )


# ========== _apply_role_transition 单元测试 ==========

def test_apply_role_transition_promote_to_admin():
    """non-admin → admin: quota=-1, model_group_ids='[]', changed 含 auto=promoted"""
    user = _make_user(UserRole.user, quota=5000, quota_used=200,
                      model_group_ids='["g1"]')
    changed = {}

    result = _apply_role_transition(user, "admin", changed)

    assert result is True
    assert user.role == UserRole.admin
    assert user.quota == -1
    assert user.model_group_ids == "[]"
    assert changed == {
        "role": "admin",
        "quota": -1,
        "model_group_ids": [],
        "auto": "promoted_to_admin",
    }


def test_apply_role_transition_demote_from_admin():
    """admin → non-admin: quota=0, model_group_ids='[]', changed 含 auto=demoted"""
    user = _make_user(UserRole.admin, quota=-1, quota_used=999,
                      model_group_ids='["g1","g2"]')
    changed = {}

    result = _apply_role_transition(user, "user", changed)

    assert result is True
    assert user.role == UserRole.user
    assert user.quota == 0
    assert user.model_group_ids == "[]"
    assert changed == {
        "role": "user",
        "quota": 0,
        "model_group_ids": [],
        "auto": "demoted_from_admin",
    }


def test_apply_role_transition_no_op_same_role():
    """同 role：不做事，changed 留空"""
    user = _make_user(UserRole.user, quota=1000)
    changed = {}

    result = _apply_role_transition(user, "user", changed)

    assert result is False
    assert user.quota == 1000  # 未变
    assert changed == {}


def test_apply_role_transition_invalid_role_returns_false():
    """非法 role 字符串：返回 False（让后续 Pydantic/UserRole 抛 422）"""
    user = _make_user(UserRole.user)
    changed = {}

    result = _apply_role_transition(user, "ghost", changed)

    assert result is False
    assert user.role == UserRole.user
    assert changed == {}


# ========== create_user 端点集成（mocked DB） ==========

def _mock_db_for_create_user(existing_username=None, existing_email=None):
    db = MagicMock()
    # query(User).filter(...).first() → first call: username check, second: email check
    db.query.return_value.filter.return_value.first.side_effect = [
        existing_username,
        existing_email,
    ]
    # mock db.refresh(user)：SQLAlchemy 真实 refresh 会从 DB 加载字段；
    # 这里手动填充 created_at 和 quota_used 让 AdminUserResponse schema 通过
    from datetime import datetime
    def _refresh(obj):
        obj.created_at = datetime.now()
        obj.quota_used = obj.quota_used if obj.quota_used is not None else 0
    db.refresh.side_effect = _refresh
    return db


def test_create_admin_user_force_quota_minus_one():
    """role='admin' 时 quota 强制 -1，model_group_ids 强制 '[]'"""
    from app.api.v1.admin import create_user

    db = _mock_db_for_create_user()
    operator = _make_user(UserRole.admin, quota=-1)
    user_data = AdminUserCreate(
        username="newadmin",
        email="na@example.com",
        password="hashedpass",
        role="admin",
        quota=100_000_000,  # 即使传了 quota，也被忽略
        model_group_ids=["mg_xxx", "mg_yyy"],  # 即使传了分组，也被忽略
    )

    _run_async(create_user(
        request=MagicMock(),
        user_data=user_data,
        db=db,
        admin=operator,
    ))

    # 找到被 add 的 User 对象
    added = db.add.call_args_list[0][0][0]
    assert isinstance(added, User)
    assert added.role == UserRole.admin
    assert added.quota == -1  # 被强制覆盖
    assert added.model_group_ids == "[]"  # 被强制覆盖
    db.commit.assert_called()


def test_create_normal_user_no_override():
    """role='user' 时 quota 和 model_group_ids 走 user_data 原值"""
    from app.api.v1.admin import create_user

    db = _mock_db_for_create_user()
    operator = _make_user(UserRole.admin)
    user_data = AdminUserCreate(
        username="newuser",
        email="nu@example.com",
        password="hashedpass",
        role="user",
        quota=5000,
        model_group_ids=["mg_a"],
    )

    _run_async(create_user(
        request=MagicMock(),
        user_data=user_data,
        db=db,
        admin=operator,
    ))

    added = db.add.call_args_list[0][0][0]
    assert added.role == UserRole.user
    assert added.quota == 5000  # 不被覆盖
    assert added.model_group_ids == '["mg_a"]'  # 不被覆盖


def test_create_user_default_role_is_user():
    """role 未指定 → 默认 user，quota 走 user_data.quota"""
    from app.api.v1.admin import create_user

    db = _mock_db_for_create_user()
    operator = _make_user(UserRole.admin)
    user_data = AdminUserCreate(
        username="d",
        email="d@x.com",
        password="hashedpass",
        quota=2000,
    )

    _run_async(create_user(
        request=MagicMock(),
        user_data=user_data,
        db=db,
        admin=operator,
    ))

    added = db.add.call_args_list[0][0][0]
    assert added.role == UserRole.user
    assert added.quota == 2000


# ========== update_user 端点集成 ==========

def _find_existing_user(user: User):
    """构造 db.query(User).filter(user_id==...).first() → user"""
    db = MagicMock()
    # 第一次 query：找 user（按 user_id）；后面 query 是 username/email 唯一性检查
    db.query.return_value.filter.return_value.first.side_effect = [
        user,
        None,  # username uniqueness
        None,  # email uniqueness
    ]
    return db


def test_promote_to_admin_sets_quota_minus_one():
    """user→admin: quota 自动 -1，model_group_ids 自动 '[]'，audit detail 含 auto=promoted"""
    from app.api.v1.admin import update_user

    user = _make_user(UserRole.user, quota=3000, quota_used=500,
                      model_group_ids='["mg_x"]')
    db = _find_existing_user(user)
    operator = _make_user(UserRole.admin)
    user_data = AdminUserUpdate(role="admin")  # 只改 role

    _run_async(update_user(
        request=MagicMock(),
        user_id=user.user_id,
        user_data=user_data,
        db=db,
        admin=operator,
    ))

    assert user.role == UserRole.admin
    assert user.quota == -1
    assert user.model_group_ids == "[]"
    db.commit.assert_called()


def test_demote_from_admin_resets_quota_and_groups():
    """admin→user: quota 自动 0，model_group_ids 自动 '[]'，audit detail 含 auto=demoted"""
    from app.api.v1.admin import update_user

    user = _make_user(UserRole.admin, quota=-1, quota_used=100,
                      model_group_ids='["mg_a","mg_b"]')
    db = _find_existing_user(user)
    operator = _make_user(UserRole.admin)
    user_data = AdminUserUpdate(role="user")

    _run_async(update_user(
        request=MagicMock(),
        user_id=user.user_id,
        user_data=user_data,
        db=db,
        admin=operator,
    ))

    assert user.role == UserRole.user
    assert user.quota == 0
    assert user.model_group_ids == "[]"
    db.commit.assert_called()


def test_admin_self_attr_change_still_blocked():
    """admin 用户，无 role transition，试图改 email → 400"""
    from fastapi import HTTPException
    from app.api.v1.admin import update_user

    user = _make_user(UserRole.admin, quota=-1)
    db = _find_existing_user(user)
    operator = _make_user(UserRole.admin)
    user_data = AdminUserUpdate(email="new@x.com")

    with pytest.raises(HTTPException) as exc_info:
        _run_async(update_user(
            request=MagicMock(),
            user_id=user.user_id,
            user_data=user_data,
            db=db,
            admin=operator,
        ))

    assert exc_info.value.status_code == 400
    assert "不能编辑管理员用户" in exc_info.value.detail


def test_admin_no_change_at_all_allowed():
    """admin 用户，只发空 AdminUserUpdate（所有字段 None）→ 200，不触发锁"""
    from app.api.v1.admin import update_user

    user = _make_user(UserRole.admin, quota=-1)
    db = _find_existing_user(user)
    operator = _make_user(UserRole.admin)
    user_data = AdminUserUpdate()  # 所有字段 None

    result = _run_async(update_user(
        request=MagicMock(),
        user_id=user.user_id,
        user_data=user_data,
        db=db,
        admin=operator,
    ))

    assert result == {"message": "更新成功"}
    db.commit.assert_called()


def test_promote_to_admin_with_other_fields_allowed():
    """user→admin 时允许同时改 email（transition 优先于 admin 内部锁）"""
    from app.api.v1.admin import update_user

    user = _make_user(UserRole.user, quota=3000)
    db = _find_existing_user(user)
    operator = _make_user(UserRole.admin)
    user_data = AdminUserUpdate(role="admin", email="new@x.com")

    _run_async(update_user(
        request=MagicMock(),
        user_id=user.user_id,
        user_data=user_data,
        db=db,
        admin=operator,
    ))

    assert user.role == UserRole.admin
    assert user.email == "new@x.com"
    assert user.quota == -1


# ========== adjust_user_quota 端点 ==========

def test_adjust_quota_on_admin_returns_400():
    """对 admin 调用 adjust_user_quota → 400"""
    from fastapi import HTTPException
    from app.api.v1.admin import adjust_user_quota

    user = _make_user(UserRole.admin, quota=-1)
    db = MagicMock()
    db.query.return_value.filter.return_value.first.return_value = user
    operator = _make_user(UserRole.admin)
    quota_data = QuotaAdjustRequest(amount=1000, reason="test")

    with pytest.raises(HTTPException) as exc_info:
        _run_async(adjust_user_quota(
            request=MagicMock(),
            user_id=user.user_id,
            quota_data=quota_data,
            db=db,
            admin=operator,
        ))

    assert exc_info.value.status_code == 400
    assert "管理员" in exc_info.value.detail


def test_adjust_quota_on_admin_set_unlimited_also_returns_400():
    """对 admin 调用 set_unlimited=true 也 400（admin 不接受手工 unlimited）"""
    from fastapi import HTTPException
    from app.api.v1.admin import adjust_user_quota

    user = _make_user(UserRole.admin, quota=0)
    db = MagicMock()
    db.query.return_value.filter.return_value.first.return_value = user
    operator = _make_user(UserRole.admin)
    quota_data = QuotaAdjustRequest(set_unlimited=True, reason="test")

    with pytest.raises(HTTPException) as exc_info:
        _run_async(adjust_user_quota(
            request=MagicMock(),
            user_id=user.user_id,
            quota_data=quota_data,
            db=db,
            admin=operator,
        ))

    assert exc_info.value.status_code == 400


def test_adjust_quota_on_normal_user_passes_admin_check():
    """普通用户调用 adjust_user_quota 不会触发 admin 锁（回归）"""
    from app.api.v1.admin import adjust_user_quota

    user = _make_user(UserRole.user, quota=5000, quota_used=200)
    db = MagicMock()
    db.query.return_value.filter.return_value.first.return_value = user
    operator = _make_user(UserRole.admin)
    quota_data = QuotaAdjustRequest(amount=1000, reason="add quota")

    # 这里会走完整 adjust_user_quota 流程（含通知等），所以用 MagicMock 隔离副作用
    # 我们只验证：没有抛 admin 锁的 HTTPException(400, "管理员...")
    try:
        _run_async(adjust_user_quota(
            request=MagicMock(),
            user_id=user.user_id,
            quota_data=quota_data,
            db=db,
            admin=operator,
        ))
    except Exception as e:
        # 可能因为 mock 不全抛别的异常；只要不是 admin 锁的 400 就算通过
        if isinstance(e, Exception) and "管理员" in str(e):
            pytest.fail("普通用户不应触发 admin 锁")
    # 进一步断言 user.quota 被增加到 6000
    assert user.quota == 6000
