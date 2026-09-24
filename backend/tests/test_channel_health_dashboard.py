import json
import asyncio
from datetime import datetime, timedelta
from types import SimpleNamespace

from starlette.requests import Request

from app.models.channel import Channel, ChannelHealthStatus, ChannelStatus
from app.models.usage_log import UsageLog
from app.services.route_health_service import RouteHealthService
from app.api.v1.health import recover_channel_health
from app.models.operation_log import OperationLog


def _channel(db, channel_id="ch_health"):
    channel = Channel(
        channel_id=channel_id,
        name="Health channel",
        type="openai",
        endpoint="https://example.com",
        api_key="sk-test",
        status=ChannelStatus.active,
        health_status=ChannelHealthStatus.healthy,
        key_health=json.dumps({"fingerprint": {"failure_count": 4, "cooldown_until": "2099-01-01T00:00:00"}}),
        cooldown_until=datetime.utcnow() + timedelta(minutes=5),
    )
    db.add(channel)
    db.commit()
    return channel


def test_channel_health_aggregates_success_error_and_latency_windows(db):
    channel = _channel(db)
    now = datetime.utcnow()
    db.add_all([
        UsageLog(log_id="usage_ok", user_id="u", key_id="k", channel_id=channel.channel_id,
                 model="m", status_code=200, latency_ms=100, created_at=now - timedelta(minutes=2)),
        UsageLog(log_id="usage_error", user_id="u", key_id="k", channel_id=channel.channel_id,
                 model="m", status_code=503, latency_ms=600, error_message="upstream unavailable",
                 created_at=now - timedelta(minutes=2)),
    ])
    db.commit()

    item = RouteHealthService(db).get_channel_health(channel.channel_id)[0]

    assert item["windows"]["5m"] == {
        "requests": 2, "successes": 1, "errors": 1,
        "success_rate": 50.0, "error_rate": 50.0,
        "p50_latency_ms": 350.0, "p95_latency_ms": 575.0,
    }
    assert item["recent_error"] == "upstream unavailable"
    assert item["cooldown"]["channel_until"] is not None
    assert item["cooldown"]["keys"] == [{"key": "fingerprint", "cooldown_until": "2099-01-01T00:00:00"}]


def test_recover_channel_clears_channel_and_key_cooldowns(db):
    channel = _channel(db, "ch_recover")

    result = RouteHealthService(db).recover_channel(channel)

    db.refresh(channel)
    assert result is True
    assert channel.cooldown_until is None
    assert json.loads(channel.key_health)["fingerprint"] == {"failure_count": 0, "cooldown_until": None}


def test_recover_endpoint_writes_operation_log(db):
    channel = _channel(db, "ch_logged_recover")
    request = Request({
        "type": "http", "method": "POST", "path": "/api/v1/admin/health/channels/ch_logged_recover/recover",
        "headers": [], "client": ("127.0.0.1", 1234), "scheme": "http", "server": ("test", 80),
    })

    asyncio.run(recover_channel_health(
        channel.channel_id, request, db, SimpleNamespace(user_id="admin_1", username="admin"),
    ))

    log = db.query(OperationLog).filter_by(action="recover_cooldown", target_id=channel.channel_id).one()
    assert json.loads(log.detail) == {"channel_id": channel.channel_id, "channel_cooldown": True, "key_cooldowns": True}
