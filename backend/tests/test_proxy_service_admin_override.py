"""
测试 admin 角色在 ProxyService 中的特权短路：
- get_effective_model_group_ids(user) 对 admin 返回全部启用分组，其他角色使用指定分组或默认分组
- check_quota(user, ...) 对 admin 永远 allowed=True，reason="admin_unlimited"

策略：纯单元 + mock（参考 test_user_unlimited_quota.py 模式），无 DB 依赖。
"""
import json
from unittest.mock import MagicMock

import pytest

import app.models  # noqa: F401, E402
from app.models.user import User, UserRole, UserStatus
from app.services.proxy_service import ProxyService


def _make_user(role: UserRole, model_group_ids: str = "[]", quota: int = 0, quota_used: int = 0) -> User:
    return User(
        user_id=f"u_{role.value}",
        username=f"{role.value}_test",
        email=f"{role.value}@test.com",
        password="h",
        role=role,
        status=UserStatus.active,
        quota=quota,
        quota_used=quota_used,
        model_group_ids=model_group_ids,
    )


def _mock_groups(group_ids):
    """构造 db.query(ModelGroup).filter(...).all() 返回的 group 列表"""
    out = []
    for gid in group_ids:
        m = MagicMock()
        m.group_id = gid
        out.append(m)
    return out


def _make_db_with_groups(group_ids):
    db = MagicMock()
    db.query.return_value.filter.return_value.all.return_value = _mock_groups(group_ids)
    return db


# ========== get_effective_model_group_ids ==========

@pytest.mark.parametrize("assigned", ["[]", '["g_vip"]', None])
def test_admin_get_effective_group_ids_returns_all_active(assigned):
    user = _make_user(UserRole.admin, model_group_ids=assigned)
    service = ProxyService(_make_db_with_groups(["g_default", "g_vip", "g_other"]))
    assert service.get_effective_model_group_ids(user) == {"g_default", "g_vip", "g_other"}


@pytest.mark.parametrize("role", [role for role in UserRole if role != UserRole.admin])
@pytest.mark.parametrize("assigned", ['["g_vip"]', '["g_vip", "g_extra"]', "[]", None])
def test_effective_groups_use_assignments_or_default(role, assigned):
    user = _make_user(role, model_group_ids=assigned)
    svc = ProxyService(_make_db_with_groups(["g_default"]))

    expected = set(json.loads(assigned or "[]")) or {"g_default"}
    assert svc.get_effective_model_group_ids(user) == expected


# ========== check_quota ==========

def _make_api_key():
    k = MagicMock()
    return k


def test_admin_check_quota_unlimited_with_zero_quota():
    """admin + quota=0 → admin 短路优先于 quota_zero，allowed=True, reason='admin_unlimited'。"""
    user = _make_user(UserRole.admin, quota=0, quota_used=0)
    svc = ProxyService(db=MagicMock())

    result = svc.check_quota(user, _make_api_key(), estimated_tokens=1000)

    assert result == {
        "allowed": True,
        "reason": "admin_unlimited",
        "message": "管理员账户为无限制额度",
    }


def test_admin_check_quota_unlimited_with_normal_quota():
    """admin + quota=100M + quota_used=50M → 仍 admin_unlimited（证明 admin 短路优先于"quota 余额不足"分支）。"""
    user = _make_user(UserRole.admin, quota=100_000_000, quota_used=50_000_000)
    svc = ProxyService(db=MagicMock())

    result = svc.check_quota(user, _make_api_key(), estimated_tokens=1_000_000)

    assert result["allowed"] is True
    assert result["reason"] == "admin_unlimited"


def test_non_admin_check_quota_quota_zero_still_rejected():
    """非 admin + quota=0 → 仍返回 quota_zero（回归原行为）。"""
    user = _make_user(UserRole.user, quota=0, quota_used=0)
    svc = ProxyService(db=MagicMock())

    result = svc.check_quota(user, _make_api_key(), estimated_tokens=1000)

    assert result["allowed"] is False
    assert result["reason"] == "quota_zero"


def test_non_admin_check_quota_unlimited_still_works():
    """非 admin + quota=-1 → 仍走原 unlimited 分支，reason='unlimited'（回归原行为，不被 admin 短路吞掉）。"""
    user = _make_user(UserRole.user, quota=-1, quota_used=999)
    svc = ProxyService(db=MagicMock())

    result = svc.check_quota(user, _make_api_key(), estimated_tokens=1000)

    assert result["allowed"] is True
    assert result["reason"] == "unlimited"
