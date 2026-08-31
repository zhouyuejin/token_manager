"""
用量同步服务 - 供应商配额同步
"""
import json
import time
from abc import ABC, abstractmethod
from datetime import datetime
from typing import Dict, Any, Optional
import httpx
from sqlalchemy.orm import Session

from app.models.provider import Provider
from app.models.provider_quota import ProviderQuota, QuotaType, SyncStatus


class BaseQuotaSyncAdapter(ABC):
    """用量同步适配器基类"""
    
    def __init__(self, provider: Provider):
        self.provider = provider
    
    @abstractmethod
    async def fetch_quota(self) -> Dict[str, Any]:
        #  endpoint={self.provider.endpoint}, api_key={self.provider.api_key[:10]}..." if self.provider.api_key else "None")
        """
        获取配额信息
        返回格式: {
            "hourly": {"limit": int, "used": int},
            "weekly": {"limit": int, "used": int}
        }
        """
        pass
    
    @abstractmethod
    def get_provider_type(self) -> str:
        """返回供应商类型标识"""
        pass


class VolcengineAdapter(BaseQuotaSyncAdapter):
    """火山方舟用量同步适配器"""
    
    def get_provider_type(self) -> str:
        return "volcengine"
    
    async def fetch_quota(self) -> Dict[str, Any]:
        #  endpoint={self.provider.endpoint}, api_key={self.provider.api_key[:10]}..." if self.provider.api_key else "None")
        """获取火山方舟用量"""
        # 火山方舟API获取用量
        # 具体实现需要根据火山方舟的API文档
        url = f"{self.provider.endpoint}/v1/quota"
        
        headers = {
            "Authorization": f"Bearer {self.provider.api_key}",
            "Content-Type": "application/json"
        }
        
        try:
            async with httpx.AsyncClient(timeout=30) as client:
                response = await client.get(url, headers=headers)
                
                if response.status_code == 200:
                    data = response.json()
                    return {
                        "hourly": {
                            "limit": data.get("hourly_limit", 0),
                            "used": data.get("hourly_used", 0)
                        },
                        "weekly": {
                            "limit": data.get("weekly_limit", 0),
                            "used": data.get("weekly_used", 0)
                        }
                    }
        except Exception as e:
            print(f"火山方舟用量同步失败: {e}")
        
        # 返回默认值（如果API调用失败）
        return {
            "hourly": {"limit": self.provider.quota_hourly, "used": 0},
            "weekly": {"limit": self.provider.quota_weekly, "used": 0}
        }


class OpenAIAdapter(BaseQuotaSyncAdapter):
    """OpenAI用量同步适配器"""
    
    def get_provider_type(self) -> str:
        return "openai"
    
    async def fetch_quota(self) -> Dict[str, Any]:
        #  endpoint={self.provider.endpoint}, api_key={self.provider.api_key[:10]}..." if self.provider.api_key else "None")
        """获取OpenAI用量"""
        # OpenAI API获取使用量
        url = "https://api.openai.com/v1/usage"
        
        today = datetime.now().strftime("%Y-%m-%d")
        
        params = {
            "date": today
        }
        
        headers = {
            "Authorization": f"Bearer {self.provider.api_key}",
            "Content-Type": "application/json"
        }
        
        try:
            async with httpx.AsyncClient(timeout=30) as client:
                response = await client.get(url, headers=headers, params=params)
                
                if response.status_code == 200:
                    data = response.json()
                    # OpenAI返回的是累计使用量
                    return {
                        "hourly": {
                            "limit": 0,  # OpenAI不提供小时限制
                            "used": data.get("total_usage", 0) // 100  # cents to dollars
                        },
                        "weekly": {
                            "limit": 0,
                            "used": data.get("total_usage", 0) // 100
                        }
                    }
        except Exception as e:
            print(f"OpenAI用量同步失败: {e}")
        
        return {
            "hourly": {"limit": 0, "used": 0},
            "weekly": {"limit": 0, "used": 0}
        }


class AnthropicAdapter(BaseQuotaSyncAdapter):
    """Anthropic用量同步适配器"""
    
    def get_provider_type(self) -> str:
        return "anthropic"
    
    async def fetch_quota(self) -> Dict[str, Any]:
        #  endpoint={self.provider.endpoint}, api_key={self.provider.api_key[:10]}..." if self.provider.api_key else "None")
        """获取Anthropic用量"""
        # Anthropic API获取使用量
        url = "https://api.anthropic.com/v1/organizations/self/usage"
        
        headers = {
            "x-api-key": self.provider.api_key,
            "anthropic-version": "2023-06-01"
        }
        
        try:
            async with httpx.AsyncClient(timeout=30) as client:
                response = await client.get(url, headers=headers)
                
                if response.status_code == 200:
                    data = response.json()
                    return {
                        "hourly": {
                            "limit": 0,
                            "used": data.get("credits_used", 0)
                        },
                        "weekly": {
                            "limit": 0,
                            "used": data.get("credits_used", 0)
                        }
                    }
        except Exception as e:
            print(f"Anthropic用量同步失败: {e}")
        
        return {
            "hourly": {"limit": 0, "used": 0},
            "weekly": {"limit": 0, "used": 0}
        }


class AzureAdapter(BaseQuotaSyncAdapter):
    """Azure OpenAI用量同步适配器"""
    
    def get_provider_type(self) -> str:
        return "azure"
    
    async def fetch_quota(self) -> Dict[str, Any]:
        #  endpoint={self.provider.endpoint}, api_key={self.provider.api_key[:10]}..." if self.provider.api_key else "None")
        """获取Azure用量"""
        # Azure需要通过Azure Monitor或Usage API获取
        # 这里是一个简化实现
        return {
            "hourly": {"limit": self.provider.quota_hourly, "used": 0},
            "weekly": {"limit": self.provider.quota_weekly, "used": 0}
        }



class MinimaxAdapter(BaseQuotaSyncAdapter):
    """Minimax用量同步适配器"""
    
    def get_provider_type(self) -> str:
        return "minimax"
    
    async def fetch_quota(self) -> Dict[str, Any]:
        """获取Minimax用量"""
        # Minimax API: GET https://www.minimaxi.com/v1/token_plan/remains
        url = "https://www.minimaxi.com/v1/token_plan/remains"
        
        headers = {
            "Authorization": f"Bearer {self.provider.api_key}",
            "Content-Type": "application/json"
        }
        
        try:
            async with httpx.AsyncClient(timeout=30) as client:
                response = await client.get(url, headers=headers)
                
                if response.status_code == 200:
                    data = response.json()
                    
                    # 解析 model_remains 获取用量
                    model_remains = data.get("model_remains", [])
                    # 当前周期总数
                    used_hourly = sum(item.get("current_interval_total_count", 0) for item in model_remains)
                    # 每周总数
                    used_weekly = sum(item.get("current_weekly_total_count", 0) for item in model_remains)
                    
                    return {
                        "hourly": {
                            "limit": self.provider.quota_hourly,
                            "used": used_hourly
                        },
                        "weekly": {
                            "limit": self.provider.quota_weekly,
                            "used": used_weekly
                        },
                        "raw_data": data
                    }
                else:
                    print(f"Minimax用量同步失败: HTTP {response.status_code}")
        except Exception as e:
            print(f"Minimax用量同步失败: {e}")
        
        # 返回默认值（如果API调用失败）
        return {
            "hourly": {"limit": self.provider.quota_hourly, "used": 0},
            "weekly": {"limit": self.provider.quota_weekly, "used": 0}
        }


    


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
    
    def get_adapter(self, provider: Provider) -> Optional[BaseQuotaSyncAdapter]:
        """获取对应的适配器"""
        adapter_class = self.ADAPTERS.get(provider.type.value)
        if adapter_class:
            return adapter_class(provider)
        return None
    
    async def sync_provider_quota(self, provider: Provider) -> bool:
        """同步单个供应商的配额"""
        adapter = self.get_adapter(provider)
        if not adapter:
            print(f"不支持的供应商类型: {provider.type.value}")
            return False
        
        try:
            quota_data = await adapter.fetch_quota()
            
            # 更新小时配额
            hourly_quota = self.db.query(ProviderQuota).filter(
                ProviderQuota.provider_id == provider.provider_id,
                ProviderQuota.quota_type == QuotaType.hourly
            ).first()
            
            if not hourly_quota:
                hourly_quota = ProviderQuota(
                    provider_id=provider.provider_id,
                    quota_type=QuotaType.hourly
                )
                self.db.add(hourly_quota)
            
            hourly_data = quota_data.get("hourly", {})
            hourly_quota.quota_limit = hourly_data.get("limit", 0)
            hourly_quota.quota_used = hourly_data.get("used", 0)
            hourly_quota.quota_remain = hourly_quota.quota_limit - hourly_quota.quota_used
            if hourly_quota.quota_limit > 0:
                hourly_quota.quota_percent = (hourly_quota.quota_used / hourly_quota.quota_limit) * 100
            else:
                hourly_quota.quota_percent = 0
            hourly_quota.sync_at = datetime.now()
            hourly_quota.sync_status = SyncStatus.success
            hourly_quota.raw_data = json.dumps(quota_data.get("raw_data")) if quota_data.get("raw_data") else None
            
            # 更新周配额
            weekly_quota = self.db.query(ProviderQuota).filter(
                ProviderQuota.provider_id == provider.provider_id,
                ProviderQuota.quota_type == QuotaType.weekly
            ).first()
            
            if not weekly_quota:
                weekly_quota = ProviderQuota(
                    provider_id=provider.provider_id,
                    quota_type=QuotaType.weekly
                )
                self.db.add(weekly_quota)
            
            weekly_data = quota_data.get("weekly", {})
            weekly_quota.quota_limit = weekly_data.get("limit", 0)
            weekly_quota.quota_used = weekly_data.get("used", 0)
            weekly_quota.quota_remain = weekly_quota.quota_limit - weekly_quota.quota_used
            if weekly_quota.quota_limit > 0:
                weekly_quota.quota_percent = (weekly_quota.quota_used / weekly_quota.quota_limit) * 100
            else:
                weekly_quota.quota_percent = 0
            weekly_quota.sync_at = datetime.now()
            weekly_quota.sync_status = SyncStatus.success
            weekly_quota.raw_data = json.dumps(quota_data.get("raw_data")) if quota_data.get("raw_data") else None
            
            self.db.commit()
            return True
            
        except Exception as e:
            print(f"同步供应商 {provider.name} 配额失败: {e}")
            # 更新同步状态为失败
            hourly_quota = self.db.query(ProviderQuota).filter(
                ProviderQuota.provider_id == provider.provider_id,
                ProviderQuota.quota_type == QuotaType.hourly
            ).first()
            if hourly_quota:
                hourly_quota.sync_status = SyncStatus.failed
                hourly_quota.sync_error = str(e)
            
            weekly_quota = self.db.query(ProviderQuota).filter(
                ProviderQuota.provider_id == provider.provider_id,
                ProviderQuota.quota_type == QuotaType.weekly
            ).first()
            if weekly_quota:
                weekly_quota.sync_status = SyncStatus.failed
                weekly_quota.sync_error = str(e)
            
            self.db.commit()
            return False
    
    async def sync_all_providers(self) -> Dict[str, int]:
        """同步所有供应商的配额"""
        providers = self.db.query(Provider).filter(
            Provider.status == "active",
            Provider.sync_enabled == 1
        ).all()
        
        success_count = 0
        failed_count = 0
        
        for provider in providers:
            if await self.sync_provider_quota(provider):
                success_count += 1
            else:
                failed_count += 1
        
        return {
            "total": len(providers),
            "success": success_count,
            "failed": failed_count
        }


def create_sync_service(db: Session) -> QuotaSyncService:
    """创建用量同步服务"""
    return QuotaSyncService(db)
