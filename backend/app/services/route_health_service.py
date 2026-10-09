"""渠道路由健康指标和 cooldown 管理。"""
import json
from datetime import datetime, timedelta

from app.models.channel import Channel
from app.models.usage_log import UsageLog
from app.services.upstream_errors import format_upstream_error


class RouteHealthService:
    WINDOWS = {"5m": timedelta(minutes=5), "1h": timedelta(hours=1), "24h": timedelta(hours=24)}

    def __init__(self, db):
        self.db = db

    @staticmethod
    def _percentile(values, percentile):
        if not values:
            return None
        values = sorted(values)
        position = (len(values) - 1) * percentile
        lower = int(position)
        upper = min(lower + 1, len(values) - 1)
        return round(values[lower] + (values[upper] - values[lower]) * (position - lower), 1)

    def _window(self, rows, since):
        rows = [row for row in rows if row.created_at and row.created_at >= since]
        latencies = [max(0, row.latency_ms or 0) for row in rows]
        requests = len(rows)
        successes = sum(row.status_code == 200 for row in rows)
        errors = requests - successes
        return {
            "requests": requests,
            "successes": successes,
            "errors": errors,
            "success_rate": round(successes * 100 / requests, 1) if requests else 0.0,
            "error_rate": round(errors * 100 / requests, 1) if requests else 0.0,
            "p50_latency_ms": self._percentile(latencies, 0.5),
            "p95_latency_ms": self._percentile(latencies, 0.95),
        }

    @staticmethod
    def _cooldown(channel):
        try:
            health = json.loads(channel.key_health or "{}")
        except (TypeError, json.JSONDecodeError):
            health = {}
        keys = [
            {"key": fingerprint, "cooldown_until": record.get("cooldown_until")}
            for fingerprint, record in health.items()
            if isinstance(record, dict) and record.get("cooldown_until")
        ]
        return {"channel_until": channel.cooldown_until, "keys": keys}

    def get_channel_health(self, channel_id=None):
        query = self.db.query(Channel)
        if channel_id:
            query = query.filter(Channel.channel_id == channel_id)
        channels = query.order_by(Channel.priority.desc(), Channel.channel_id.asc()).all()
        now = datetime.utcnow()
        result = []
        for channel in channels:
            rows = self.db.query(UsageLog).filter(UsageLog.channel_id == channel.channel_id).all()
            ordered_rows = sorted(rows, key=lambda row: (row.created_at or datetime.min, row.id or 0), reverse=True)
            recent_failure = next((row for row in ordered_rows if row.status_code != 200 and row.error_message), None)
            billing_failure = None
            for row in ordered_rows:
                if row.status_code == 200:
                    break
                error = format_upstream_error(channel.type, row.status_code, raw_text=row.error_message or "")
                if any(reason in error for reason in ("账户余额不足", "预付费余额已用完", "账单或支付信息异常")):
                    billing_failure = error
                    break
            health_status = channel.health_status.value if hasattr(channel.health_status, "value") else str(channel.health_status)
            recent_error = format_upstream_error(channel.type, recent_failure.status_code, raw_text=recent_failure.error_message) if recent_failure else None
            result.append({
                "channel_id": channel.channel_id,
                "name": channel.name,
                "status": channel.status.value if hasattr(channel.status, "value") else str(channel.status),
                "health_status": "unhealthy" if billing_failure else health_status,
                "last_check_at": channel.last_check_at,
                "cooldown": self._cooldown(channel),
                "recent_error": billing_failure or recent_error,
                "windows": {name: self._window(rows, now - duration) for name, duration in self.WINDOWS.items()},
            })
        return result

    def recover_channel(self, channel):
        channel.cooldown_until = None
        try:
            health = json.loads(channel.key_health or "{}")
        except (TypeError, json.JSONDecodeError):
            health = {}
        for record in health.values():
            if isinstance(record, dict):
                record["failure_count"] = 0
                record["cooldown_until"] = None
        channel.key_health = json.dumps(health) if health else None
        self.db.commit()
        return True
