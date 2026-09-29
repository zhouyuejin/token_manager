from prometheus_client import CONTENT_TYPE_LATEST, CollectorRegistry, Counter, Gauge, generate_latest


registry = CollectorRegistry()
rate_limit_rejections = Counter(
    "token_rate_limit_rejections_total", "Requests rejected by rate limits", ("window",), registry=registry
)
budget_rejections = Counter(
    "token_budget_rejections_total", "Requests rejected by budget admission", ("scope_type",), registry=registry
)
route_decisions = Counter(
    "token_route_decisions_total", "Completed routing decisions", ("model", "channel_id", "success"), registry=registry
)
channel_cooldowns = Counter(
    "token_channel_cooldowns_total", "Channel cooldown activations", registry=registry
)
active_channel_cooldowns = Gauge(
    "token_active_channel_cooldowns", "Channels currently in cooldown", registry=registry
)
budget_usage = Gauge(
    "token_budget_usage_ratio", "Budget used plus reserved divided by configured amount", ("scope_type",), registry=registry
)


def render_metrics():
    return generate_latest(registry), CONTENT_TYPE_LATEST
