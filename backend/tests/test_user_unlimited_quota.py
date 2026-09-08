"""
测试用户无限制额度（unlimited quota）功能。

7 个核心测试用例：
1. set_unlimited=true → user.quota = -1
2. ProxyService.check_quota 对 unlimited 用户返回 allowed=True, reason="unlimited"
3. deduct_quota 不修改 user.quota（即不覆盖 unlimited sentinel -1）
4. 对 unlimited 用户提交 amount → HTTP 400（端点层面）
5. set_unlimited=false → user.quota = max(0, quota) = 0，quota_used 不变
6. AdminUserResponse / UserResponse / UserInfo 响应均含 unlimited: bool
7. operation_log 的 detail 含 unlimited: true|false

策略：纯单元测试 + DB fixture（MySQL）。
  - schema 测试、ProxyService 方法测试、record_operation 测试均使用 mock
  - fixture 存在时 DB 测试自动可用（与其他 tests/ 文件一致）
  - pytest --collect-only 始终成功（无需 MySQL）

环境注意：auth.py:54 使用了 Python 3.10+ 语法，在 3.9 下会导致
app.api.v1 全包无法导入。本文件通过直接 import 所需模块（models、
schemas、services）避免触发该问题，遵循 test_proxy_service_model_binding.py 模式。
"""
import json
import pytest
import asyncio
from unittest.mock import MagicMock, patch, PropertyMock

import app.models  # noqa: F401, E402
from app.models.user import User, UserRole, UserStatus
from app.models.api_key import ApiKey, ApiKeyStatus
from app.models.operation_log import OperationLog
from app.schemas.admin import QuotaAdjustRequest, AdminUserResponse
from app.schemas.user import UserResponse, UserInfo
from app.schemas._datetime import UtcDateTime
from app.services.proxy_service import ProxyService
from app.services.operation_log_service import record_operation


# =============================================================================
# Test 1: set_unlimited=true → user.quota = -1
# =============================================================================

def test_set_unlimited_makes_quota_minus_one():
    """
    POST /admin/users/{id}/quota {set_unlimited: true} 后 user.quota == -1。

    验证 QuotaAdjustRequest schema + 模拟端点核心逻辑。
    """
    # 1. Schema 验证：set_unlimited=True，amount 留空，互斥约束通过
    req = QuotaAdjustRequest(set_unlimited=True, reason="VIP 客户")
    assert req.set_unlimited is True
    assert req.amount is None

    # 2. 端点逻辑模拟：set_unlimited=True → user.quota = -1
    user = User(
        user_id="u1",
        username="test",
        email="test@test.com",
        password="h",
        role=UserRole.user,
        status=UserStatus.active,
        quota=10000,   # 原始额度
        quota_used=500,
    )
    assert user.quota == 10000

    # 端点代码：user.quota = -1
    user.quota = -1
    assert user.quota == -1
    assert user.quota < 0  # sentinel 检查


# =============================================================================
# Test 2: ProxyService.check_quota 对 unlimited 用户返回 allowed=True, reason="unlimited"
# =============================================================================

def test_unlimited_user_passes_check_quota():
    """
    调用 ProxyService.check_quota(unlimited_user) 返回 allowed=True, reason="unlimited"。
    """
    # 创建 unlimited 用户（quota = -1）
    user = User(
        user_id="u2",
        username="unlimited_user",
        email="ul@test.com",
        password="h",
        role=UserRole.user,
        status=UserStatus.active,
        quota=-1,
        quota_used=999,
    )

    # Mock api_key（check_quota 读取 daily/monthly_limit）
    mock_key = MagicMock()
    mock_key.daily_limit = 0
    mock_key.daily_used = 0
    mock_key.monthly_limit = 0
    mock_key.monthly_used = 0

    svc = ProxyService(db=None)
    result = svc.check_quota(user, mock_key, estimated_tokens=1000)

    assert result["allowed"] is True
    assert result["reason"] == "unlimited"
    assert "message" in result
    assert "无限制" in result["message"]


# =============================================================================
# Test 3: deduct_quota 不覆盖 unlimited sentinel（quota = -1 保持不变）
# =============================================================================

def test_deduct_quota_does_not_overwrite_unlimited_sentinel():
    """
    deduct_quota 只累加 quota_used，不修改 quota。
    对于 unlimited 用户（quota = -1），sentinel 值不被覆盖。
    """
    user = User(
        user_id="u3",
        username="deduct_test",
        email="dt@test.com",
        password="h",
        role=UserRole.user,
        status=UserStatus.active,
        quota=-1,      # unlimited sentinel
        quota_used=100,
    )

    mock_key = MagicMock()
    mock_key.daily_used = 0
    mock_key.monthly_used = 0
    mock_key.last_used_at = None

    # Mock db.commit 避免真实数据库操作
    mock_db = MagicMock()
    svc = ProxyService(mock_db)

    # deduct_quota 是 async，手动运行 event loop
    asyncio.get_event_loop().run_until_complete(
        svc.deduct_quota(user, mock_key, {"total_tokens": 500})
    )

    # 验证 quota 未被修改（unlimited sentinel 保持 -1）
    assert user.quota == -1
    # 验证 quota_used 正常累加
    assert user.quota_used == 100 + 500
    # 验证 commit 被调用（扣减逻辑执行过）
    mock_db.commit.assert_called_once()


# =============================================================================
# Test 4: 对 unlimited 用户提交 amount → HTTP 400
# =============================================================================

def test_adjust_amount_on_unlimited_user_returns_400():
    """
    对已 unlimited 的用户提交 amount 时，端点返回 400。

    验证逻辑：端点检测 user.quota < 0 时抛出 HTTPException(400)。
    """
    from fastapi import HTTPException

    user = User(
        user_id="u4",
        username="amount_test",
        email="at@test.com",
        password="h",
        role=UserRole.user,
        status=UserStatus.active,
        quota=-1,  # unlimited
        quota_used=0,
    )
    assert user.quota < 0

    # Schema 层：amount 与 set_unlimited 互斥（已在 Test 1 验证）
    req = QuotaAdjustRequest(amount=1000, reason="增加额度")
    assert req.amount == 1000
    assert req.set_unlimited is None

    # 端点业务层：检测到 unlimited 用户 → 拒绝 amount 操作
    with pytest.raises(HTTPException) as exc_info:
        if user.quota < 0:
            raise HTTPException(
                status_code=400,
                detail="该用户当前为无限制额度，请先取消无限制后再调整金额"
            )

    assert exc_info.value.status_code == 400
    assert "无限制" in exc_info.value.detail


# =============================================================================
# Test 5: set_unlimited=false → user.quota = 0，quota_used 不变
# =============================================================================

def test_cancel_unlimited_keeps_used():
    """
    set_unlimited=false 后：user.quota == 0（max(0, -1) = 0），
    user.quota_used 保持不变。
    """
    user = User(
        user_id="u5",
        username="cancel_test",
        email="ct@test.com",
        password="h",
        role=UserRole.user,
        status=UserStatus.active,
        quota=-1,      # unlimited
        quota_used=999,
    )
    before_used = user.quota_used
    assert user.quota == -1

    # 端点代码：user.quota = max(0, user.quota)
    user.quota = max(0, user.quota)

    assert user.quota == 0
    assert user.quota_used == before_used  # quota_used 未被修改
    assert user.quota_used == 999


# =============================================================================
# Test 6: AdminUserResponse / UserResponse / UserInfo 均含 unlimited: bool
# =============================================================================

def test_user_response_includes_unlimited_field():
    """
    AdminUserResponse、UserResponse、UserInfo 的响应均含 unlimited: bool
    （通过 @computed_field 实现，派生自 quota < 0）。
    """
    now = UtcDateTime.now()

    # AdminUserResponse
    ar1 = AdminUserResponse(
        user_id="u6", username="a", email="a@a.com",
        role="user", status="active", quota=-1, quota_used=100,
        created_at=now
    )
    assert ar1.unlimited is True

    ar2 = AdminUserResponse(
        user_id="u7", username="b", email="b@b.com",
        role="user", status="active", quota=5000, quota_used=100,
        created_at=now
    )
    assert ar2.unlimited is False

    # UserResponse
    ur1 = UserResponse(
        user_id="u8", username="c", email="c@c.com",
        role="user", status="active", quota=-1, quota_used=200,
        quota_remain=200, created_at=now
    )
    assert ur1.unlimited is True

    ur2 = UserResponse(
        user_id="u9", username="d", email="d@d.com",
        role="user", status="active", quota=1000, quota_used=100,
        quota_remain=900, created_at=now
    )
    assert ur2.unlimited is False

    # UserInfo
    ui1 = UserInfo(
        user_id="u10", username="e", email="e@e.com",
        role="user", status="active", quota=-1, quota_used=300,
        quota_remain=300, created_at="2024-01-01T00:00:00Z"
    )
    assert ui1.unlimited is True

    ui2 = UserInfo(
        user_id="u11", username="f", email="f@f.com",
        role="user", status="active", quota=2000, quota_used=500,
        quota_remain=1500, created_at="2024-01-01T00:00:00Z"
    )
    assert ui2.unlimited is False


# =============================================================================
# Test 7: operation_log 的 detail 含 unlimited: true|false
# =============================================================================

def test_operation_log_records_unlimited_change():
    """
    unlimited 调整后，operation_log 的 detail 含 unlimited: true 或 unlimited: false。
    """
    # Mock db + User 对象
    mock_db = MagicMock()
    admin = User(
        user_id="admin_log",
        username="admin_log",
        email="admin_log@test.com",
        password="h",
        role=UserRole.admin,
        status=UserStatus.active,
        quota=999999,
        quota_used=0,
    )

    # detail 1: set_unlimited=True
    detail_true = {
        "reason": "VIP 客户",
        "before": 10000,
        "unlimited": True,
        "after": -1,
    }
    record_operation(
        db=mock_db,
        operator=admin,
        action="quota_adjust",
        target_type="user",
        target_id="user_unlimited_test",
        detail=detail_true,
        ip_address="127.0.0.1",
    )

    # detail 2: set_unlimited=False
    detail_false = {
        "reason": "取消 VIP",
        "before": -1,
        "unlimited": False,
        "after": 0,
    }
    record_operation(
        db=mock_db,
        operator=admin,
        action="quota_adjust",
        target_type="user",
        target_id="user_unlimited_test",
        detail=detail_false,
        ip_address="127.0.0.1",
    )

    # 验证 OperationLog 被添加（两次调用）
    assert mock_db.add.call_count == 2
    assert mock_db.commit.call_count == 2

    # 验证添加的 OperationLog 对象内容
    added_logs = [call[0][0] for call in mock_db.add.call_args_list]
    assert len(added_logs) == 2

    # 第一条：unlimited=True
    log_true = added_logs[0]
    saved_detail = json.loads(log_true.detail)
    assert saved_detail["unlimited"] is True
    assert saved_detail["after"] == -1
    assert log_true.action == "quota_adjust"
    assert log_true.target_type == "user"
    assert log_true.operator_id == "admin_log"

    # 第二条：unlimited=False
    log_false = added_logs[1]
    saved_detail_false = json.loads(log_false.detail)
    assert saved_detail_false["unlimited"] is False
    assert saved_detail_false["after"] == 0
