"""
用量同步服务 - 渠道配额同步
"""
import json
from abc import ABC, abstractmethod
from datetime import datetime, timezone
from typing import Dict, Any, Optional, List
import httpx
from sqlalchemy.orm import Session

from app.models.channel import Channel
from app.models.channel_quota import ChannelQuota, QuotaType, SyncStatus


def _parse_reset_at(value: Optional[str]) -> Optional[datetime]:
    if not value:
        return None
    try:
        return datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError:
        return None


def normalize_quota_windows(windows: List[Dict[str, Any]], now: Optional[datetime] = None) -> List[Dict[str, Any]]:
    """Normalize provider-specific quota windows to one backend contract."""
    current = now or datetime.now(timezone.utc)
    normalized = []
    for window in windows:
        limit = int(window.get("limit") or 0)
        used = window.get("used")
        remain = window.get("remain")

        if used is None and remain is not None:
            used = max(0, limit - int(remain))
        used = int(used or 0)

        if remain is None:
            remain = max(0, limit - used)
        remain = int(remain or 0)

        percent = window.get("percent")
        if percent is None:
            percent = (used / limit * 100) if limit > 0 else 0
        elif limit > 0 and window.get("used") is None and window.get("remain") is None:
            used = int(limit * float(percent) / 100)
            remain = max(0, limit - used)

        reset_at = window.get("reset_at")
        reset_dt = _parse_reset_at(reset_at)
        reset_in_seconds = window.get("reset_in_seconds")
        if reset_dt:
            if reset_dt.tzinfo is None:
                reset_dt = reset_dt.replace(tzinfo=timezone.utc)
            reset_in_seconds = max(0, int((reset_dt - current).total_seconds()))
        elif reset_in_seconds is not None:
            reset_in_seconds = max(0, int(reset_in_seconds))

        normalized.append({
            "type": window.get("type") or "custom",
            "label": window.get("label"),
            "limit": limit,
            "used": used,
            "remain": remain,
            "percent": round(float(percent), 2),
            "reset_at": reset_at,
            "reset_in_seconds": reset_in_seconds,
            "raw_data": window.get("raw_data"),
        })
    return normalized


class BaseQuotaSyncAdapter(ABC):
    """用量同步适配器基类"""
    
    def __init__(self, channel: Channel):
        self.channel = channel
    
    @abstractmethod
    async def fetch_quota(self, config: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        pass
    
    @abstractmethod
    def get_channel_type(self) -> str:
        pass


class QuotaSyncError(Exception):
    """Raised when a provider quota request fails."""


from abc import ABC, abstractmethod


class VolcengineAdapter(BaseQuotaSyncAdapter):
    """火山方舟用量同步适配器"""
    
    def get_channel_type(self) -> str:
        return "volcengine"
    
    async def fetch_quota(self, config: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        url = f"{self.channel.endpoint}/v1/quota"
        headers = {"Authorization": f"Bearer {self.channel.api_key}", "Content-Type": "application/json"}
        
        try:
            async with httpx.AsyncClient(timeout=30) as client:
                response = await client.get(url, headers=headers)
                if response.status_code == 200:
                    data = response.json()
                    windows = []
                    if data.get("hourly_limit") is not None:
                        windows.append({"type": "hourly", "label": "小时", "limit": data.get("hourly_limit", 0), "used": data.get("hourly_used", 0)})
                    if data.get("weekly_limit") is not None:
                        windows.append({"type": "weekly", "label": "本周", "limit": data.get("weekly_limit", 0), "used": data.get("weekly_used", 0)})
                    return {
                        "hourly": {"limit": data.get("hourly_limit", 0), "used": data.get("hourly_used", 0)},
                        "weekly": {"limit": data.get("weekly_limit", 0), "used": data.get("weekly_used", 0)},
                        "windows": windows,
                        "raw_data": data,
                    }
        except Exception as e:
            print(f"火山方舟用量同步失败: {e}")
        
        return {"hourly": {"limit": self.channel.quota_hourly, "used": 0}, "weekly": {"limit": self.channel.quota_weekly, "used": 0}}


class OpenAIAdapter(BaseQuotaSyncAdapter):
    """OpenAI用量同步适配器"""
    
    def get_channel_type(self) -> str:
        return "openai"
    
    async def fetch_quota(self, config: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        url = "https://api.openai.com/v1/usage"
        headers = {"Authorization": f"Bearer {self.channel.api_key}", "Content-Type": "application/json"}
        
        try:
            async with httpx.AsyncClient(timeout=30) as client:
                response = await client.get(url, headers=headers, params={"date": datetime.now().strftime("%Y-%m-%d")})
                if response.status_code == 200:
                    data = response.json()
                    used = data.get("total_usage", 0) // 100
                    return {
                        "hourly": {"limit": 0, "used": used},
                        "weekly": {"limit": 0, "used": used},
                        "windows": [
                            {"type": "daily", "label": "今日", "limit": 0, "used": used},
                        ],
                        "raw_data": data,
                    }
        except Exception as e:
            print(f"OpenAI用量同步失败: {e}")
        
        return {"hourly": {"limit": 0, "used": 0}, "weekly": {"limit": 0, "used": 0}}


class AnthropicAdapter(BaseQuotaSyncAdapter):
    """Anthropic用量同步适配器"""
    
    def get_channel_type(self) -> str:
        return "anthropic"
    
    async def fetch_quota(self, config: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        url = "https://api.anthropic.com/v1/organizations/self/usage"
        headers = {"x-api-key": self.channel.api_key, "anthropic-version": "2023-06-01"}
        
        try:
            async with httpx.AsyncClient(timeout=30) as client:
                response = await client.get(url, headers=headers)
                if response.status_code == 200:
                    data = response.json()
                    used = data.get("credits_used", 0)
                    return {
                        "hourly": {"limit": 0, "used": used},
                        "weekly": {"limit": 0, "used": used},
                        "windows": [
                            {"type": "custom", "label": "已用额度", "limit": 0, "used": used},
                        ],
                        "raw_data": data,
                    }
        except Exception as e:
            print(f"Anthropic用量同步失败: {e}")
        
        return {"hourly": {"limit": 0, "used": 0}, "weekly": {"limit": 0, "used": 0}}


class AzureAdapter(BaseQuotaSyncAdapter):
    """Azure OpenAI用量同步适配器"""
    
    def get_channel_type(self) -> str:
        return "azure"
    
    async def fetch_quota(self, config: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        return {
            "hourly": {"limit": self.channel.quota_hourly, "used": 0},
            "weekly": {"limit": self.channel.quota_weekly, "used": 0},
            "windows": [
                {"type": "hourly", "label": "小时", "limit": self.channel.quota_hourly, "used": 0},
                {"type": "weekly", "label": "本周", "limit": self.channel.quota_weekly, "used": 0},
            ],
        }


class MinimaxAdapter(BaseQuotaSyncAdapter):
    """Minimax用量同步适配器"""
    
    def get_channel_type(self) -> str:
        return "minimax"
    
    async def fetch_quota(self, config: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        base_url = (self.channel.endpoint or "https://api.minimaxi.com/v1").rstrip("/")
        url = f"{base_url}/token_plan/remains"
        headers = {"Authorization": f"Bearer {self.channel.api_key}", "Content-Type": "application/json"}
        
        try:
            async with httpx.AsyncClient(timeout=30) as client:
                response = await client.get(url, headers=headers)
                if response.status_code != 200:
                    raise QuotaSyncError(f"MiniMax 返回 HTTP {response.status_code}: {response.text[:200]}")

                data = response.json()
                payload = data.get("data") if isinstance(data.get("data"), dict) else data
                model_remains = payload.get("model_remains", [])
                if not model_remains:
                    raise QuotaSyncError(f"MiniMax 响应缺少 model_remains, 字段: {list(payload.keys()) if isinstance(payload, dict) else type(payload).__name__}")

                first = model_remains[0]
                windows = [
                    {
                        "type": "five_hour",
                        "label": "5小时",
                                "limit": first.get("current_interval_total_count", self.channel.quota_hourly),
                                "remain": first.get("current_interval_remaining_count"),
                                "percent": 100 - (first.get("current_interval_remaining_percent", 0) or 0),
                                "reset_in_seconds": int(first.get("remains_time", 0) / 1000),
                            },
                    {
                        "type": "weekly",
                        "label": "本周",
                                "limit": first.get("current_weekly_total_count", self.channel.quota_weekly),
                                "remain": first.get("current_weekly_remaining_count"),
                                "percent": 100 - (first.get("current_weekly_remaining_percent", 0) or 0),
                                "reset_in_seconds": int(first.get("weekly_remains_time", 0) / 1000),
                            },
                ]
                return {
                    "windows": windows,
                    "raw_data": data
                }
        except Exception as e:
            raise QuotaSyncError(f"MiniMax 用量同步失败: {e}") from e


class QuotaSyncService:
    """用量同步服务"""
    
    ADAPTERS = {
        "volcengine": VolcengineAdapter,
        "openai": OpenAIAdapter,
        "anthropic": AnthropicAdapter,
        "azure": AzureAdapter,
        "minimax": MinimaxAdapter,
    }
    
    def __init__(self, db: Session):
        self.db = db
    
    def get_adapter(self, channel: Channel) -> Optional[BaseQuotaSyncAdapter]:
        adapter_class = self.ADAPTERS.get(channel.type.value)
        if adapter_class:
            return adapter_class(channel)
        return None
    
    async def sync_channel_quota(self, channel: Channel) -> bool:
        """同步单个渠道的配额"""
        channel_name = channel.name
        config = json.loads(channel.quota_config) if channel.quota_config else None
        adapter = self.get_adapter(channel)
        if not adapter and not (config and config.get("query_mode") == "manual"):
            print(f"不支持的渠道类型: {channel.type.value}")
            return False
        
        try:
            if config and config.get("query_mode") == "manual":
                quota_data = {
                    "provider": "manual",
                    "windows": config.get("windows") or [],
                    "raw_data": config,
                }
            else:
                quota_data = await adapter.fetch_quota(config)
            windows = normalize_quota_windows(quota_data.get("windows") or [
                {"type": "hourly", "label": "小时", **quota_data.get("hourly", {})},
                {"type": "weekly", "label": "本周", **quota_data.get("weekly", {})},
            ])
            raw_data = quota_data.get("raw_data")
            
            for window in windows:
                quota_type = window["type"]
                quota = self.db.query(ChannelQuota).filter(
                    ChannelQuota.channel_id == channel.channel_id,
                    ChannelQuota.quota_type == quota_type
                ).first()

                if not quota:
                    quota = ChannelQuota(channel_id=channel.channel_id, quota_type=quota_type)
                    self.db.add(quota)

                quota.quota_limit = window["limit"]
                quota.quota_used = window["used"]
                quota.quota_remain = window["remain"]
                quota.quota_percent = window["percent"]
                quota.sync_at = datetime.now()
                quota.sync_status = SyncStatus.success
                quota.raw_data = json.dumps({
                    "window": window,
                    "provider": quota_data.get("provider") or channel.type.value,
                    "raw_data": raw_data,
                }, ensure_ascii=False)
            
            self.db.commit()
            return True
            
        except Exception as e:
            self.db.rollback()
            print(f"同步渠道 {channel_name} 配额失败: {e}")
            self._mark_sync_failed(channel, str(e))
            return False

    def _mark_sync_failed(self, channel: Channel, error: str) -> None:
        for quota_type in (QuotaType.hourly, QuotaType.weekly):
            quota = self.db.query(ChannelQuota).filter(
                ChannelQuota.channel_id == channel.channel_id,
                ChannelQuota.quota_type == quota_type
            ).first()
            if not quota:
                quota = ChannelQuota(channel_id=channel.channel_id, quota_type=quota_type)
                self.db.add(quota)
            quota.sync_status = SyncStatus.failed
            quota.sync_error = error[:500]
            quota.sync_at = datetime.now()
        self.db.commit()
    
    async def sync_all_channels(self) -> Dict[str, int]:
        """同步所有渠道的配额"""
        channels = self.db.query(Channel).filter(
            Channel.status == "active",
            Channel.sync_enabled == True
        ).all()
        
        success_count = 0
        for ch in channels:
            if await self.sync_channel_quota(ch):
                success_count += 1
        return {"total": len(channels), "success": success_count, "failed": len(channels) - success_count}


def create_sync_service(db: Session) -> QuotaSyncService:
    """创建用量同步服务"""
    return QuotaSyncService(db)
