import json

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
