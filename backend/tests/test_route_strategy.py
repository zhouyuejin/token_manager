from datetime import datetime, timedelta
from unittest.mock import patch

from app.models.channel import Channel, ChannelHealthStatus, ChannelStatus
from app.models.model import Model, ModelStatus
from app.models.model_channel import ModelChannel
from app.models.usage_log import UsageLog
from app.services.proxy_service import ProxyService


def _setup_routes(db, strategy="priority"):
    model = Model(model_id="strategy-model", display_name="Strategy model", route_strategy=strategy, status=ModelStatus.active)
    first = Channel(channel_id="channel-a", name="A", type="openai", endpoint="https://a.example", api_key="a", status=ChannelStatus.active, health_status=ChannelHealthStatus.healthy, priority=10)
    second = Channel(channel_id="channel-b", name="B", type="openai", endpoint="https://b.example", api_key="b", status=ChannelStatus.active, health_status=ChannelHealthStatus.healthy, priority=1)
    db.add_all([model, first, second])
    db.flush()
    db.add_all([
        ModelChannel(model_id=model.model_id, channel_id=first.channel_id, upstream_model="a", priority=0, weight=1, enabled=True),
        ModelChannel(model_id=model.model_id, channel_id=second.channel_id, upstream_model="b", priority=0, weight=100, enabled=True),
    ])
    db.commit()
    return model, first, second


def test_select_candidates_applies_model_route_strategy(db):
    model, first, second = _setup_routes(db, "lowest_latency")
    now = datetime.utcnow()
    db.add_all([
        UsageLog(log_id="latency_a", user_id="u", key_id="k", channel_id=first.channel_id, model=model.model_id, status_code=200, latency_ms=800, created_at=now - timedelta(minutes=1)),
        UsageLog(log_id="latency_b", user_id="u", key_id="k", channel_id=second.channel_id, model=model.model_id, status_code=200, latency_ms=100, created_at=now - timedelta(minutes=1)),
    ])
    db.commit()

    candidates = ProxyService(db).select_candidates(model.model_id, None, None)

    assert [channel.channel_id for channel, _, _ in candidates] == [second.channel_id, first.channel_id]


def test_select_candidates_uses_historical_cost_for_lowest_cost(db):
    model, first, second = _setup_routes(db, "lowest_cost")
    now = datetime.utcnow()
    db.add_all([
        UsageLog(log_id="cost_a", user_id="u", key_id="k", channel_id=first.channel_id, model=model.model_id, status_code=200, latency_ms=100, cost_usd=2, created_at=now - timedelta(minutes=1)),
        UsageLog(log_id="cost_b", user_id="u", key_id="k", channel_id=second.channel_id, model=model.model_id, status_code=200, latency_ms=100, cost_usd=1, created_at=now - timedelta(minutes=1)),
    ])
    db.commit()

    candidates = ProxyService(db).select_candidates(model.model_id, None, None)

    assert [channel.channel_id for channel, _, _ in candidates] == [second.channel_id, first.channel_id]


def test_select_candidates_uses_binding_weight_for_weight_strategy(db):
    model, first, second = _setup_routes(db, "weight")

    with patch("app.services.proxy_service.random.random", side_effect=[0.9, 0.1]):
        candidates = ProxyService(db).select_candidates(model.model_id, None, None)

    assert [channel.channel_id for channel, _, _ in candidates] == [second.channel_id, first.channel_id]
