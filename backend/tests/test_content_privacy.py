import json
from types import SimpleNamespace

from app.models.usage_log import UsageLog
from app.api.v1.projects import ProjectSave
from app.services.content_privacy import content_summary, redact_sensitive_text
from app.services.operation_log_service import record_operation
from app.services.proxy_service import ProxyService


def test_redact_sensitive_text_hides_credentials_and_personal_data():
    value = (
        'api_key="sk-secret123456" Authorization: Bearer top-secret-token '
        '身份证号=110105199001011234 联系电话 13800138000 alice@example.com'
    )

    redacted = redact_sensitive_text(value)

    assert "sk-secret123456" not in redacted
    assert "top-secret-token" not in redacted
    assert "110105199001011234" not in redacted
    assert "13800138000" not in redacted
    assert "alice@example.com" not in redacted
    assert "[REDACTED" in redacted


def test_content_summary_extracts_bounded_text_and_redacts():
    summary = content_summary({
        "messages": [{"role": "user", "content": "call 13800138000 with key sk-secret123456"}],
        "image_url": "data:image/png;base64,raw-image-data",
    })

    assert summary == "call [REDACTED_PHONE] with key [REDACTED_API_KEY]"
    assert "raw-image-data" not in summary
    assert len(content_summary({"prompt": "x" * 3000})) == 2000
    assert content_summary({"output": [{"content": [{"text": "response text"}]}]}) == "response text"


def test_project_content_audit_is_disabled_by_default():
    assert ProjectSave(name="Example", dept_id="dept_test").content_audit_enabled is False


def test_usage_content_is_only_stored_when_project_audit_is_enabled(db):
    service = ProxyService(db)
    request = {"messages": [{"content": "phone 13800138000; key sk-secret123456"}]}
    for key_id, enabled in (("key_disabled", False), ("key_enabled", True)):
        attribution = {"project_id": f"project_{key_id}", "department_id": "dept_test"}
        service.usage_attribution[key_id] = {**attribution, "content_audit_enabled": enabled}
        service.record_usage(
            user_id="user_test", key_id=key_id, channel_id=None, model="model_test",
            tokens={}, latency_ms=1, status_code=200, error_message="Bearer error-secret",
            attribution=attribution, request_content=request,
            response_content={"choices": [{"message": {"content": "safe response"}}]},
        )
    db.commit()

    disabled, enabled = db.query(UsageLog).order_by(UsageLog.id).all()
    assert disabled.request_summary is None
    assert disabled.response_summary is None
    assert "Bearer error-secret" not in disabled.error_message
    assert "[REDACTED" in disabled.error_message
    assert "13800138000" not in enabled.request_summary
    assert "sk-secret123456" not in enabled.request_summary
    assert enabled.response_summary == "safe response"


def test_usage_log_keeps_audit_snapshot_out_of_model_fields(db):
    service = ProxyService(db)
    service.usage_attribution["key_test"] = {
        "project_id": "project_test",
        "department_id": "dept_test",
        "content_audit_enabled": True,
    }

    service.record_usage(
        user_id="user_test", key_id="key_test", channel_id=None, model="model_test",
        tokens={}, latency_ms=1, status_code=200, request_content={"prompt": "audited"},
    )
    db.commit()

    usage = db.query(UsageLog).one()
    assert (usage.project_id, usage.department_id) == ("project_test", "dept_test")
    assert usage.request_summary == "audited"


def test_route_and_operation_logs_are_redacted_before_persistence(db):
    service = ProxyService(db)
    service.record_route_decision(
        "request_test", "user_test", "key_test", "model_test", [], {}, None, [],
        502, False, "phone 13800138000, key sk-secret123456",
    )
    record_operation(
        db, SimpleNamespace(user_id="user_test", username="13800138000"),
        "update", "channel", detail={"authorization": "Bearer operation-secret", "contact": "a@example.com"},
    )

    from app.models.operation_log import OperationLog
    from app.models.route_decision_log import RouteDecisionLog

    route = db.query(RouteDecisionLog).one()
    operation = db.query(OperationLog).one()
    assert "13800138000" not in route.error_message
    assert "sk-secret123456" not in route.error_message
    assert "13800138000" not in operation.operator_name
    detail = json.loads(operation.detail)
    assert "operation-secret" not in detail["authorization"]
    assert "a@example.com" not in detail["contact"]
