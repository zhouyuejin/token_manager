import json
from datetime import datetime, timedelta

from fastapi.testclient import TestClient

from app.models.route_decision_log import RouteDecisionLog
from app.services.proxy_service import ProxyService


def test_route_decision_log_keeps_routing_path_without_secrets_or_prompt(db):
    service = ProxyService(db)

    service.record_route_decision(
        request_id="req_test_123",
        user_id="user_1",
        key_id="key_1",
        model="gpt-test",
        candidates=["channel-a", "channel-b"],
        skipped_reasons={"channel-a": "upstream_503"},
        selected_channel="channel-b",
        retry_path=[{"channel_id": "channel-a", "status_code": 503}],
        status_code=200,
        success=True,
        error_message=None,
        prompt="must-not-be-stored",
        upstream_key="sk-upstream-secret",
    )

    row = db.query(RouteDecisionLog).filter_by(request_id="req_test_123").one()
    assert json.loads(row.candidate_channels) == ["channel-a", "channel-b"]
    assert json.loads(row.retry_path)[0]["status_code"] == 503
    serialized = json.dumps({
        "candidate_channels": row.candidate_channels,
        "skipped_reasons": row.skipped_reasons,
        "retry_path": row.retry_path,
        "error_message": row.error_message,
    })
    assert "must-not-be-stored" not in serialized
    assert "sk-upstream-secret" not in serialized


def test_route_decision_log_records_failed_request(db):
    service = ProxyService(db)

    service.record_route_decision(
        request_id="req_failed_123",
        user_id="user_1",
        key_id="key_1",
        model="gpt-test",
        candidates=[],
        skipped_reasons={},
        selected_channel=None,
        retry_path=[],
        status_code=502,
        success=False,
        error_message="无可用渠道",
    )

    row = db.query(RouteDecisionLog).filter_by(request_id="req_failed_123").one()
    assert row.success is False
    assert row.status_code == 502
    assert row.error_message == "无可用渠道"


def test_route_decision_api_redacts_secrets_and_prompt_from_error(db, monkeypatch):
    from app.core.database import get_db
    from app.dependencies import require_admin
    from app.main import app

    db.add(RouteDecisionLog(
        request_id="req_sensitive", user_id="user_1", key_id="key_1", model="gpt-test",
        candidate_channels='["channel-a"]', skipped_reasons='{}', selected_channel="channel-a",
        retry_path='[]', status_code=502, success=False,
        error_message="invalid api_key sk-abcdefghijklmnopqrstuvwxyz123456; prompt: private user text",
    ))
    db.commit()
    app.dependency_overrides[get_db] = lambda: db
    app.dependency_overrides[require_admin] = lambda: object()
    try:
        response = TestClient(app).get("/api/v1/admin/logs/routes", params={"request_id": "req_sensitive"})
    finally:
        app.dependency_overrides.pop(get_db, None)
        app.dependency_overrides.pop(require_admin, None)

    assert response.status_code == 200
    error = response.json()["items"][0]["error_message"]
    assert "sk-abcdefghijklmnopqrstuvwxyz123456" not in error
    assert "private user text" not in error
    assert error == "上游错误包含敏感内容，已隐藏"


def test_route_decision_search_filters_by_request_and_routing_fields(db, monkeypatch):
    from app.core.database import get_db
    from app.dependencies import require_admin
    from app.main import app

    now = datetime.utcnow()
    rows = [
        RouteDecisionLog(
            request_id="req_match", user_id="user_1", key_id="key_1", model="gpt-test",
            candidate_channels='["channel-a"]', skipped_reasons='{}', selected_channel="channel-a",
            retry_path='[]', status_code=200, success=True, created_at=now,
        ),
        RouteDecisionLog(
            request_id="req_other", user_id="user_2", key_id="key_2", model="other-model",
            candidate_channels='["channel-b"]', skipped_reasons='{}', selected_channel="channel-b",
            retry_path='[]', status_code=502, success=False, created_at=now - timedelta(seconds=1),
        ),
    ]
    db.add_all(rows)
    db.commit()
    app.dependency_overrides[get_db] = lambda: db
    app.dependency_overrides[require_admin] = lambda: object()
    try:
        response = TestClient(app).get("/api/v1/admin/logs/routes", params={
            "request_id": "req_match", "user_id": "user_1", "key_id": "key_1",
            "model": "gpt-test", "channel_id": "channel-a", "status_code": 200,
        })
    finally:
        app.dependency_overrides.pop(get_db, None)
        app.dependency_overrides.pop(require_admin, None)

    assert response.status_code == 200
    assert response.json()["total"] == 1
    item = response.json()["items"][0]
    assert item["request_id"] == "req_match"
    assert item["candidate_channels"] == ["channel-a"]
    assert item["retry_path"] == []
