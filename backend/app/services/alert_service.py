"""Configurable, deduplicated in-app operational alerts."""
import json
import secrets
from datetime import datetime, timedelta
from decimal import Decimal
from sqlalchemy import func
from app.models.alert import AlertState
from app.models.channel import Channel
from app.models.channel_quota import ChannelQuota, SyncStatus
from app.models.notification import Notification, NotificationType
from app.models.project import Project
from app.models.usage_log import UsageLog
from app.models.user import User, UserRole
from app.services.ws_manager import manager

DEFAULTS = {"channel_error_rate_percent": 50.0, "channel_error_min_requests": 5,
            "quota_remaining_percent": 20.0, "project_growth_multiplier": 3.0,
            "project_growth_min_cost_usd": 0.01}

class AlertService:
    def __init__(self, db): self.db = db

    def config(self):
        from app.models.system_config import SystemConfig
        row = self.db.query(SystemConfig).filter_by(config_key="alert_rules").first()
        return {**DEFAULTS, **(json.loads(row.config_value) if row and row.config_value else {})}

    async def _set(self, key, kind, target, active, value, title, content, metadata):
        state = self.db.query(AlertState).filter_by(alert_key=key).first()
        if not state:
            state = AlertState(alert_key=key, alert_type=kind, target_id=target)
            self.db.add(state); self.db.flush()
        changed = state.active != active
        state.active, state.last_value = active, str(value)
        if not changed:
            self.db.commit(); return
        recipients = {uid for uid, in self.db.query(User.user_id).filter(User.role == UserRole.admin).all()}
        if kind == "project":
            owner = self.db.query(Project.owner_user_id).filter(Project.project_id == target).scalar()
            if owner: recipients.add(owner)
        verb = "恢复" if not active else "告警"
        for uid in recipients:
            self.db.add(Notification(notif_id="notif_" + secrets.token_hex(8), user_id=uid,
                type=NotificationType.system, title=f"{verb}：{title}", content=content,
                extra_data=json.dumps({**metadata, "active": active}), is_read=0))
        self.db.commit()
        for uid in recipients:
            notif = self.db.query(Notification).filter_by(user_id=uid).order_by(Notification.id.desc()).first()
            if notif:
                try: await manager.send_to_user(uid, {"type": "new_notification", "notif": notif.to_dict()})
                except Exception: pass

    async def check(self):
        cfg, now = self.config(), datetime.utcnow()
        since = now - timedelta(minutes=5)
        for channel in self.db.query(Channel).all():
            rows = self.db.query(UsageLog).filter(UsageLog.channel_id == channel.channel_id,
                UsageLog.created_at >= since).all()
            rate = sum(row.status_code != 200 for row in rows) * 100 / len(rows) if rows else 0
            active = len(rows) >= cfg["channel_error_min_requests"] and rate >= cfg["channel_error_rate_percent"]
            await self._set(f"channel_error:{channel.channel_id}", "channel", channel.channel_id, active, rate,
                f"渠道错误率过高（{channel.name}）", f"最近 5 分钟请求 {len(rows)} 次，错误率 {rate:.1f}%。",
                {"kind": "channel_error_rate", "channel_id": channel.channel_id, "error_rate": round(rate, 1)})
        for quota in self.db.query(ChannelQuota).filter(ChannelQuota.sync_status == SyncStatus.success,
                ChannelQuota.quota_limit > 0).all():
            remain = float(quota.quota_remain or 0) * 100 / float(quota.quota_limit)
            await self._set(f"quota_low:{quota.channel_id}:{quota.quota_type.value}", "quota", quota.channel_id,
                remain <= cfg["quota_remaining_percent"], remain, "上游配额不足",
                f"渠道 {quota.channel_id} 的 {quota.quota_type.value} 配额剩余 {remain:.1f}%。",
                {"kind": "upstream_quota_low", "channel_id": quota.channel_id, "remaining_percent": round(remain, 1)})
        current_start, baseline_start = now - timedelta(hours=1), now - timedelta(hours=25)
        totals = self.db.query(UsageLog.project_id, func.sum(UsageLog.cost_usd)).filter(
            UsageLog.project_id.isnot(None), UsageLog.status_code == 200, UsageLog.created_at >= baseline_start
        ).group_by(UsageLog.project_id).all()
        for project_id, total in totals:
            project_name = self.db.query(Project.name).filter(Project.project_id == project_id).scalar() or project_id
            current = self.db.query(func.coalesce(func.sum(UsageLog.cost_usd), 0)).filter(
                UsageLog.project_id == project_id, UsageLog.status_code == 200, UsageLog.created_at >= current_start).scalar() or 0
            current, baseline = Decimal(current), (Decimal(total or 0) - Decimal(current)) / 24
            active = current >= Decimal(str(cfg["project_growth_min_cost_usd"])) and (baseline == 0 or current >= baseline * Decimal(str(cfg["project_growth_multiplier"])))
            ratio = float(current / baseline) if baseline else (float("inf") if current else 0)
            await self._set(f"project_growth:{project_id}", "project", project_id, active, ratio,
                "项目用量异常增长", f"项目 {project_name} 最近 1 小时消费 ${current:.8f}，约为历史小时均值的 {ratio:.1f} 倍。",
                {"kind": "project_usage_growth", "project_id": project_id, "ratio": ratio})
