import json
import asyncio

import pytest
from fastapi import HTTPException
from starlette.requests import Request

from app.api.v1.alerts import AlertRuleConfig, get_alert_rules, update_alert_rules
from app.dependencies import require_admin
from app.models.operation_log import OperationLog
from app.models.notification import Notification
from app.models.role_permission import RolePermission
from app.models.user import User, UserRole, UserStatus
from app.services.alert_service import AlertService


def make_request(method="GET"):
    return Request({
        "type": "http", "method": method, "path": "/api/v1/admin/alerts/rules",
        "headers": [], "query_string": b"", "server": ("test", 80), "scheme": "http",
    })


def make_user(role):
    return User(
        user_id=f"usr_{role.value}", username=role.value, email=f"{role.value}@example.com",
        password="x", role=role, status=UserStatus.active,
    )


def test_alert_rules_update_is_audited_and_used_by_alert_service(db):
    admin = make_user(UserRole.admin)
    data = AlertRuleConfig(
        channel_error_rate_percent=40,
        channel_error_min_requests=8,
        quota_remaining_percent=15,
        project_growth_multiplier=2.5,
        project_growth_min_cost_cny=0.05,
    )

    result = update_alert_rules(data, make_request("PUT"), db, admin)

    assert result == data.model_dump()
    assert get_alert_rules(db, admin) == data.model_dump()
    assert AlertService(db).config() == data.model_dump()
    log = db.query(OperationLog).filter_by(action="update", target_type="alert_rules").one()
    assert json.loads(log.detail) == {"before": {
        "channel_error_rate_percent": 50.0,
        "channel_error_min_requests": 5,
        "quota_remaining_percent": 20.0,
        "project_growth_multiplier": 3.0,
        "project_growth_min_cost_cny": 0.01,
    }, "after": data.model_dump()}


def test_auditor_can_read_alert_rules_but_cannot_update(db):
    db.add(RolePermission(role="auditor", permission="admin:read"))
    db.commit()
    auditor = make_user(UserRole.auditor)

    assert require_admin(make_request(), auditor, db) is auditor
    with pytest.raises(HTTPException) as exc:
        require_admin(make_request("PUT"), auditor, db)
    assert exc.value.status_code == 403


def test_alert_trigger_and_recovery_notifications_are_deduplicated(db):
    db.add(make_user(UserRole.admin))
    db.commit()
    service = AlertService(db)

    for active in (True, True, False, False):
        asyncio.run(service._set(
            "test_alert", "channel", "channel_test", active, 75,
            "测试告警", "测试告警内容", {"kind": "test"},
        ))

    assert db.query(Notification).count() == 2
