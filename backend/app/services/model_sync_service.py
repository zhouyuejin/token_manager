"""
模型同步服务 - 从渠道API获取模型列表
"""
import json
import httpx
from abc import ABC, abstractmethod
from datetime import datetime
from typing import Dict, Any, List, Optional
from sqlalchemy.orm import Session

from app.models.channel import Channel, ChannelType


class ModelInfo:
    """模型信息"""
    def __init__(self, model_id: str, name: str = None, owned_by: str = None):
        self.model_id = model_id
        self.name = name or model_id
        self.owned_by = owned_by or ""
    
    def to_dict(self) -> Dict[str, Any]:
        return {"model_id": self.model_id, "name": self.name, "owned_by": self.owned_by}


class BaseModelSyncAdapter(ABC):
    """模型同步适配器基类"""
    
    def __init__(self, channel: Channel):
        self.channel = channel
    
    @abstractmethod
    async def fetch_models(self) -> List[ModelInfo]:
        pass
    
    def get_headers(self) -> Dict[str, str]:
        return {"Authorization": f"Bearer {self.channel.api_key}", "Content-Type": "application/json"}


class OpenAIModelAdapter(BaseModelSyncAdapter):
    """OpenAI模型同步适配器"""
    
    async def fetch_models(self) -> List[ModelInfo]:
        url = f"{self.channel.endpoint}/v1/models"
        try:
            async with httpx.AsyncClient(timeout=30) as client:
                response = await client.get(url, headers=self.get_headers())
                if response.status_code == 200:
                    data = response.json()
                    return [ModelInfo(model_id=item["id"], name=item.get("id", ""), owned_by="openai") for item in data.get("data", [])]
        except Exception as e:
            print(f"OpenAI模型同步失败: {e}")
        return self._get_default_models()
    
    def _get_default_models(self) -> List[ModelInfo]:
        return [ModelInfo("gpt-4o", "GPT-4o", "openai"), ModelInfo("gpt-4o-mini", "GPT-4o Mini", "openai"),
                ModelInfo("gpt-4-turbo", "GPT-4 Turbo", "openai"), ModelInfo("gpt-4", "GPT-4", "openai"),
                ModelInfo("gpt-3.5-turbo", "GPT-3.5 Turbo", "openai")]


class AnthropicModelAdapter(BaseModelSyncAdapter):
    """Anthropic模型同步适配器"""
    
    def get_headers(self) -> Dict[str, str]:
        return {"x-api-key": self.channel.api_key, "anthropic-version": "2023-06-01"}
    
    async def fetch_models(self) -> List[ModelInfo]:
        url = "https://api.anthropic.com/v1/models"
        try:
            async with httpx.AsyncClient(timeout=30) as client:
                response = await client.get(url, headers=self.get_headers())
                if response.status_code == 200:
                    data = response.json()
                    return [ModelInfo(model_id=item["id"], name=item.get("display_name", item["id"]), owned_by="anthropic") for item in data.get("data", [])]
        except Exception as e:
            print(f"Anthropic模型同步失败: {e}")
        return self._get_default_models()
    
    def _get_default_models(self) -> List[ModelInfo]:
        return [ModelInfo("claude-3-5-sonnet-20241022", "Claude 3.5 Sonnet", "anthropic"),
                ModelInfo("claude-3-opus-20240229", "Claude 3 Opus", "anthropic"),
                ModelInfo("claude-3-sonnet-20240229", "Claude 3 Sonnet", "anthropic"),
                ModelInfo("claude-3-haiku-20240307", "Claude 3 Haiku", "anthropic")]


class MinimaxModelAdapter(BaseModelSyncAdapter):
    """Minimax模型同步适配器"""
    
    # MiniMax 官方模型名称映射（API 调用时使用官方名称）
    MODEL_NAME_MAP = {
        "MiniMax-M2.7": "MiniMax-M2.7",
        "MiniMax-M3": "MiniMax-M3",
        "MiniMax-M3-Speed": "MiniMax-M3-Speed",
        # 兼容旧名称（如果 API 返回旧格式）
        "abab6.5s-chat": "MiniMax-M3",
        "abab6.5g-chat": "MiniMax-M3-Speed",
    }
    
    async def fetch_models(self) -> List[ModelInfo]:
        url = f"{self.channel.endpoint}/models"
        try:
            async with httpx.AsyncClient(timeout=30) as client:
                response = await client.get(url, headers=self.get_headers())
                if response.status_code == 200:
                    data = response.json()
                    return [ModelInfo(model_id=item["id"], name=self.MODEL_NAME_MAP.get(item["id"], item["id"]), owned_by="minimax") for item in data.get("data", [])]
        except Exception as e:
            print(f"Minimax模型同步失败: {e}")
        return self._get_default_models()
    
    def _get_default_models(self) -> List[ModelInfo]:
        # MiniMax 官方支持的模型（根据官方文档）
        return [
            ModelInfo("MiniMax-M2.7", "MiniMax-M2.7", "minimax"),
            ModelInfo("MiniMax-M3", "MiniMax-M3", "minimax"),
            ModelInfo("MiniMax-M3-Speed", "MiniMax-M3-Speed", "minimax"),
        ]


class DeepseekModelAdapter(BaseModelSyncAdapter):
    """Deepseek模型同步适配器"""
    
    async def fetch_models(self) -> List[ModelInfo]:
        url = f"{self.channel.endpoint}/v1/models"
        try:
            async with httpx.AsyncClient(timeout=30) as client:
                response = await client.get(url, headers=self.get_headers())
                if response.status_code == 200:
                    data = response.json()
                    return [ModelInfo(model_id=item["id"], name=item.get("id", ""), owned_by="deepseek") for item in data.get("data", [])]
        except Exception as e:
            print(f"Deepseek模型同步失败: {e}")
        return self._get_default_models()
    
    def _get_default_models(self) -> List[ModelInfo]:
        return [ModelInfo("deepseek-chat", "DeepSeek Chat", "deepseek"), ModelInfo("deepseek-coder", "DeepSeek Coder", "deepseek")]


class AzureModelAdapter(BaseModelSyncAdapter):
    """Azure OpenAI模型同步适配器"""
    
    async def fetch_models(self) -> List[ModelInfo]:
        return self._get_default_models()
    
    def _get_default_models(self) -> List[ModelInfo]:
        return [ModelInfo("gpt-4", "GPT-4 (Azure)", "azure"), ModelInfo("gpt-35-turbo", "GPT-3.5 Turbo (Azure)", "azure")]


class VolcengineModelAdapter(BaseModelSyncAdapter):
    """火山引擎模型同步适配器"""

    async def fetch_models(self) -> List[ModelInfo]:
        base = (self.channel.endpoint or "").rstrip("/")
        # coding plan 端点用 /v3/models，普通端点用 /v1/models
        models_path = "/v3/models" if "/api/coding" in base else "/v1/models"
        url = f"{base}{models_path}"
        try:
            async with httpx.AsyncClient(timeout=30) as client:
                response = await client.get(url, headers=self.get_headers())
                if response.status_code == 200:
                    data = response.json()
                    # 过滤 Shutdown 状态的模型
                    return [
                        ModelInfo(model_id=item.get("id", ""), name=item.get("id", ""), owned_by="volcengine")
                        for item in data.get("data", [])
                        if item.get("status") != "Shutdown"
                    ]
        except Exception as e:
            print(f"火山引擎模型同步失败: {e}")
        return self._get_default_models()
    
    def _get_default_models(self) -> List[ModelInfo]:
        return [ModelInfo("doubao-pro-32k", "豆包 Pro 32K", "volcengine"), ModelInfo("doubao-lite-4k", "豆包 Lite 4K", "volcengine")]


class CustomModelAdapter(BaseModelSyncAdapter):
    """自定义渠道模型同步适配器"""
    
    async def fetch_models(self) -> List[ModelInfo]:
        url = f"{self.channel.endpoint}/v1/models"
        try:
            async with httpx.AsyncClient(timeout=30) as client:
                response = await client.get(url, headers=self.get_headers())
                if response.status_code == 200:
                    data = response.json()
                    return [ModelInfo(model_id=item["id"], name=item.get("id", ""), owned_by=self.channel.type.value) for item in data.get("data", [])]
        except Exception as e:
            print(f"自定义渠道模型同步失败: {e}")
        return []


MODEL_SYNC_ADAPTERS = {
    "openai": OpenAIModelAdapter, "anthropic": AnthropicModelAdapter,
    "minimax": MinimaxModelAdapter, "deepseek": DeepseekModelAdapter,
    "azure": AzureModelAdapter, "volcengine": VolcengineModelAdapter,
    "custom": CustomModelAdapter,
}


class ModelSyncService:
    """模型同步服务"""
    
    def __init__(self, db: Session):
        self.db = db
    
    def get_adapter(self, channel: Channel) -> BaseModelSyncAdapter:
        adapter_class = MODEL_SYNC_ADAPTERS.get(channel.type.value)
        return adapter_class(channel) if adapter_class else CustomModelAdapter(channel)
    
    async def sync_channel_models(self, channel: Channel) -> Dict[str, Any]:
        """同步单个渠道的模型列表"""
        adapter = self.get_adapter(channel)
        try:
            models = await adapter.fetch_models()
            return {"success": True, "count": len(models), "models": [m.to_dict() for m in models], "message": f"成功同步 {len(models)} 个模型"}
        except Exception as e:
            return {"success": False, "count": 0, "models": [], "message": f"同步失败: {str(e)}"}
    
    async def sync_all_channels(self) -> Dict[str, Any]:
        """同步所有渠道的模型列表"""
        channels = self.db.query(Channel).filter(Channel.status == "active").all()
        results = []
        success_count = fail_count = 0
        for ch in channels:
            result = await self.sync_channel_models(ch)
            results.append({"channel_id": ch.channel_id, "channel_name": ch.name, **result})
            if result["success"]: success_count += 1
            else: fail_count += 1
        return {"total": len(channels), "success": success_count, "failed": fail_count, "results": results}


def create_model_sync_service(db: Session) -> ModelSyncService:
    return ModelSyncService(db)
