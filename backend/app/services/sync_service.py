"""
用量同步服务 - 渠道配额同步
"""
import json
from datetime import datetime
from typing import Dict, Any, Optional
import httpx
from sqlalchemy.orm import Session

from app.models.channel import Channel
from app.models.channel_quota import ChannelQuota, QuotaType, SyncStatus


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
                    return {
                        "hourly": {"limit": data.get("hourly_limit", 0), "used": data.get("hourly_used", 0)},
                        "weekly": {"limit": data.get("weekly_limit", 0), "used": data.get("weekly_used", 0)}
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
                    return {
                        "hourly": {"limit": 0, "used": data.get("total_usage", 0) // 100},
                        "weekly": {"limit": 0, "used": data.get("total_usage", 0) // 100}
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
                    return {
                        "hourly": {"limit": 0, "used": data.get("credits_used", 0)},
                        "weekly": {"limit": 0, "used": data.get("credits_used", 0)}
                    }
        except Exception as e:
            print(f"Anthropic用量同步失败: {e}")
        
        return {"hourly": {"limit": 0, "used": 0}, "weekly": {"limit": 0, "used": 0}}


class AzureAdapter(BaseQuotaSyncAdapter):
    """Azure OpenAI用量同步适配器"""
    
    def get_channel_type(self) -> str:
        return "azure"
    
    async def fetch_quota(self, config: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        return {"hourly": {"limit": self.channel.quota_hourly, "used": 0}, "weekly": {"limit": self.channel.quota_weekly, "used": 0}}


class MinimaxAdapter(BaseQuotaSyncAdapter):
    """Minimax用量同步适配器"""
    
    def get_channel_type(self) -> str:
        return "minimax"
    
    async def fetch_quota(self, config: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        url = "https://www.minimaxi.com/v1/token_plan/remains"
        headers = {"Authorization": f"Bearer {self.channel.api_key}", "Content-Type": "application/json"}
        
        try:
            async with httpx.AsyncClient(timeout=30) as client:
                response = await client.get(url, headers=headers)
                if response.status_code == 200:
                    data = response.json()
                    model_remains = data.get("model_remains", [])
                    return {
                        "hourly": {"limit": self.channel.quota_hourly, "used": sum(i.get("current_interval_total_count", 0) for i in model_remains)},
                        "weekly": {"limit": self.channel.quota_weekly, "used": sum(i.get("current_weekly_total_count", 0) for i in model_remains)},
                        "raw_data": data
                    }
        except Exception as e:
            print(f"Minimax用量同步失败: {e}")
        
        return {"hourly": {"limit": self.channel.quota_hourly, "used": 0}, "weekly": {"limit": self.channel.quota_weekly, "used": 0}}


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
        adapter = self.get_adapter(channel)
        if not adapter:
            print(f"不支持的渠道类型: {channel.type.value}")
            return False
        
        config = json.loads(channel.quota_config) if channel.quota_config else None
        
        try:
            quota_data = await adapter.fetch_quota(config)
            
            # 更新小时配额
            hourly_quota = self.db.query(ChannelQuota).filter(
                ChannelQuota.channel_id == channel.channel_id,
                ChannelQuota.quota_type == QuotaType.hourly
            ).first()
            
            if not hourly_quota:
                hourly_quota = ChannelQuota(channel_id=channel.channel_id, quota_type=QuotaType.hourly)
                self.db.add(hourly_quota)
            
            hourly_data = quota_data.get("hourly", {})
            hourly_quota.quota_limit = hourly_data.get("limit", 0)
            hourly_quota.quota_used = hourly_data.get("used", 0)
            hourly_quota.quota_remain = hourly_quota.quota_limit - hourly_quota.quota_used
            hourly_quota.quota_percent = (hourly_quota.quota_used / hourly_quota.quota_limit * 100) if hourly_quota.quota_limit > 0 else 0
            hourly_quota.sync_at = datetime.now()
            hourly_quota.sync_status = SyncStatus.success
            hourly_quota.raw_data = json.dumps(quota_data.get("raw_data")) if quota_data.get("raw_data") else None
            
            # 更新周配额
            weekly_quota = self.db.query(ChannelQuota).filter(
                ChannelQuota.channel_id == channel.channel_id,
                ChannelQuota.quota_type == QuotaType.weekly
            ).first()
            
            if not weekly_quota:
                weekly_quota = ChannelQuota(channel_id=channel.channel_id, quota_type=QuotaType.weekly)
                self.db.add(weekly_quota)
            
            weekly_data = quota_data.get("weekly", {})
            weekly_quota.quota_limit = weekly_data.get("limit", 0)
            weekly_quota.quota_used = weekly_data.get("used", 0)
            weekly_quota.quota_remain = weekly_quota.quota_limit - weekly_quota.quota_used
            weekly_quota.quota_percent = (weekly_quota.quota_used / weekly_quota.quota_limit * 100) if weekly_quota.quota_limit > 0 else 0
            weekly_quota.sync_at = datetime.now()
            weekly_quota.sync_status = SyncStatus.success
            weekly_quota.raw_data = json.dumps(quota_data.get("raw_data")) if quota_data.get("raw_data") else None
            
            self.db.commit()
            return True
            
        except Exception as e:
            print(f"同步渠道 {channel.name} 配额失败: {e}")
            self.db.rollback()
            return False
    
    async def sync_all_channels(self) -> Dict[str, int]:
        """同步所有渠道的配额"""
        channels = self.db.query(Channel).filter(
            Channel.status == "active",
            Channel.sync_enabled == True
        ).all()
        
        success_count = sum(1 for ch in channels if self.db.execute(self.sync_channel_quota(ch)))
        return {"total": len(channels), "success": success_count, "failed": len(channels) - success_count}


def create_sync_service(db: Session) -> QuotaSyncService:
    """创建用量同步服务"""
    return QuotaSyncService(db)
