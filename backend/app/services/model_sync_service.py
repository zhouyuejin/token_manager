"""
模型同步服务 - 从供应商API获取模型列表
"""
import json
import httpx
from abc import ABC, abstractmethod
from datetime import datetime
from typing import Dict, Any, List, Optional
from sqlalchemy.orm import Session

from app.models.provider import Provider, ProviderType


class ModelInfo:
    """模型信息"""
    def __init__(self, model_id: str, name: str = None, owned_by: str = None):
        self.model_id = model_id
        self.name = name or model_id
        self.owned_by = owned_by or ""
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "model_id": self.model_id,
            "name": self.name,
            "owned_by": self.owned_by
        }


class BaseModelSyncAdapter(ABC):
    """模型同步适配器基类"""
    
    def __init__(self, provider: Provider):
        self.provider = provider
    
    @abstractmethod
    async def fetch_models(self) -> List[ModelInfo]:
        """
        获取上游模型列表
        返回: List[ModelInfo]
        """
        pass
    
    def get_headers(self) -> Dict[str, str]:
        """获取认证头 - 子类可重写"""
        return {
            "Authorization": f"Bearer {self.provider.api_key}",
            "Content-Type": "application/json"
        }


class OpenAIModelAdapter(BaseModelSyncAdapter):
    """OpenAI模型同步适配器"""
    
    async def fetch_models(self) -> List[ModelInfo]:
        # 如果配置了Group ID，添加到URL参数
        if self.provider.group_id:
            url = f"{self.provider.endpoint}/v1/models?GroupId={self.provider.group_id}"
        else:
            url = f"{self.provider.endpoint}/v1/models"
        
        try:
            async with httpx.AsyncClient(timeout=30) as client:
                response = await client.get(url, headers=self.get_headers())
                
                if response.status_code == 200:
                    data = response.json()
                    models = []
                    for item in data.get("data", []):
                        models.append(ModelInfo(
                            model_id=item["id"],
                            name=item.get("id", ""),
                            owned_by="openai"
                        ))
                    return models
        except Exception as e:
            print(f"OpenAI模型同步失败: {e}")
        
        return self._get_default_models()
    
    def _get_default_models(self) -> List[ModelInfo]:
        """返回默认模型列表"""
        return [
            ModelInfo("gpt-4o", "GPT-4o", "openai"),
            ModelInfo("gpt-4o-mini", "GPT-4o Mini", "openai"),
            ModelInfo("gpt-4-turbo", "GPT-4 Turbo", "openai"),
            ModelInfo("gpt-4", "GPT-4", "openai"),
            ModelInfo("gpt-3.5-turbo", "GPT-3.5 Turbo", "openai"),
        ]


class AnthropicModelAdapter(BaseModelSyncAdapter):
    """Anthropic模型同步适配器"""
    
    def get_headers(self) -> Dict[str, str]:
        return {
            "x-api-key": self.provider.api_key,
            "anthropic-version": "2023-06-01"
        }
    
    async def fetch_models(self) -> List[ModelInfo]:
        url = "https://api.anthropic.com/v1/models"
        
        try:
            async with httpx.AsyncClient(timeout=30) as client:
                response = await client.get(url, headers=self.get_headers())
                
                if response.status_code == 200:
                    data = response.json()
                    models = []
                    for item in data.get("data", []):
                        models.append(ModelInfo(
                            model_id=item["id"],
                            name=item.get("display_name", item["id"]),
                            owned_by="anthropic"
                        ))
                    return models
        except Exception as e:
            print(f"Anthropic模型同步失败: {e}")
        
        return self._get_default_models()
    
    def _get_default_models(self) -> List[ModelInfo]:
        return [
            ModelInfo("claude-3-opus-20240229", "Claude 3 Opus", "anthropic"),
            ModelInfo("claude-3-sonnet-20240229", "Claude 3 Sonnet", "anthropic"),
            ModelInfo("claude-3-haiku-20240307", "Claude 3 Haiku", "anthropic"),
            ModelInfo("claude-2.1", "Claude 2.1", "anthropic"),
            ModelInfo("claude-2.0", "Claude 2.0", "anthropic"),
        ]


class MinimaxModelAdapter(BaseModelSyncAdapter):
    """Minimax模型同步适配器"""
    
    # 模型ID映射：将API返回的ID映射为友好的显示名称
    MODEL_NAME_MAP = {
        # MiniMax M3 系列
        "abab6.5s-chat": "MiniMax-M3",
        "abab6.5g-chat": "MiniMax-M3-Speed",
        "abab6.5s-chat-200k": "MiniMax-M3-200K",
        "abab6.5g-chat-200k": "MiniMax-M3-Speed-200K",
        
        # MiniMax M2.7 系列
        "abab2.7s-chat": "MiniMax-M2.7",
        "abab2.7g-chat": "MiniMax-M2.7-Speed",
        "abab2.7s-chat-200k": "MiniMax-M2.7-200K",
        "abab2.7g-chat-200k": "MiniMax-M2.7-Speed-200K",
        
        # MiniMax M2.5 系列
        "abab5.5s-chat": "MiniMax-M2.5",
        "abab5.5g-chat": "MiniMax-M2.5-Speed",
        "abab5.5s-chat-200k": "MiniMax-M2.5-200K",
        "abab5.5g-chat-200k": "MiniMax-M2.5-Speed-200K",
        
        # MiniMax M2.1 系列
        "abab2.1s-chat": "MiniMax-M2.1",
        "abab2.1g-chat": "MiniMax-M2.1-Speed",
        "abab2.1s-chat-200k": "MiniMax-M2.1-200K",
        "abab2.1g-chat-200k": "MiniMax-M2.1-Speed-200K",
        
        # MiniMax M2 系列
        "abab5s-chat": "MiniMax-M2",
        "abab5g-chat": "MiniMax-M2-Speed",
        
        # MiniMax M1 系列
        "abab4-chat": "MiniMax-M1",
    }
    
    async def fetch_models(self) -> List[ModelInfo]:
        # 如果配置了Group ID，添加到URL参数
        if self.provider.group_id:
            url = f"{self.provider.endpoint}/v1/models?GroupId={self.provider.group_id}"
        else:
            url = f"{self.provider.endpoint}/v1/models"
        
        try:
            async with httpx.AsyncClient(timeout=30) as client:
                response = await client.get(url, headers=self.get_headers())
                
                if response.status_code == 200:
                    data = response.json()
                    models = []
                    for item in data.get("data", []):
                        model_id = item["id"]
                        # 使用映射表转换名称
                        display_name = self.MODEL_NAME_MAP.get(model_id, model_id)
                        models.append(ModelInfo(
                            model_id=model_id,
                            name=display_name,
                            owned_by="minimax"
                        ))
                    return models
        except Exception as e:
            print(f"Minimax模型同步失败: {e}")
        
        return self._get_default_models()
    
    def _get_default_models(self) -> List[ModelInfo]:
        return [
            ModelInfo("abab6.5s-chat", "MiniMax-M3", "minimax"),
            ModelInfo("abab6.5g-chat", "MiniMax-M3-Speed", "minimax"),
            ModelInfo("abab5.5s-chat", "MiniMax-M2", "minimax"),
            ModelInfo("abab5.5g-chat", "MiniMax-M2-Speed", "minimax"),
            ModelInfo("abab4-chat", "MiniMax-M1", "minimax"),
        ]


class DeepseekModelAdapter(BaseModelSyncAdapter):
    """Deepseek模型同步适配器"""
    
    async def fetch_models(self) -> List[ModelInfo]:
        # 如果配置了Group ID，添加到URL参数
        if self.provider.group_id:
            url = f"{self.provider.endpoint}/v1/models?GroupId={self.provider.group_id}"
        else:
            url = f"{self.provider.endpoint}/v1/models"
        
        try:
            async with httpx.AsyncClient(timeout=30) as client:
                response = await client.get(url, headers=self.get_headers())
                
                if response.status_code == 200:
                    data = response.json()
                    models = []
                    for item in data.get("data", []):
                        models.append(ModelInfo(
                            model_id=item["id"],
                            name=item.get("id", ""),
                            owned_by="deepseek"
                        ))
                    return models
        except Exception as e:
            print(f"Deepseek模型同步失败: {e}")
        
        return self._get_default_models()
    
    def _get_default_models(self) -> List[ModelInfo]:
        return [
            ModelInfo("deepseek-chat", "DeepSeek Chat", "deepseek"),
            ModelInfo("deepseek-coder", "DeepSeek Coder", "deepseek"),
        ]


class AzureModelAdapter(BaseModelSyncAdapter):
    """Azure OpenAI模型同步适配器"""
    
    async def fetch_models(self) -> List[ModelInfo]:
        # Azure需要通过不同的方式获取模型列表
        # 这里返回默认模型，实际应该通过Azure资源部署API获取
        return self._get_default_models()
    
    def _get_default_models(self) -> List[ModelInfo]:
        return [
            ModelInfo("gpt-4", "GPT-4 (Azure)", "azure"),
            ModelInfo("gpt-4-32k", "GPT-4 32K (Azure)", "azure"),
            ModelInfo("gpt-35-turbo", "GPT-3.5 Turbo (Azure)", "azure"),
        ]


class VolcengineModelAdapter(BaseModelSyncAdapter):
    """火山引擎模型同步适配器"""
    
    async def fetch_models(self) -> List[ModelInfo]:
        # 如果配置了Group ID，添加到URL参数
        if self.provider.group_id:
            url = f"{self.provider.endpoint}/v1/models?GroupId={self.provider.group_id}"
        else:
            url = f"{self.provider.endpoint}/v1/models"
        
        try:
            async with httpx.AsyncClient(timeout=30) as client:
                response = await client.get(url, headers=self.get_headers())
                
                if response.status_code == 200:
                    data = response.json()
                    models = []
                    for item in data.get("data", []):
                        models.append(ModelInfo(
                            model_id=item.get("id", ""),
                            name=item.get("id", ""),
                            owned_by="volcengine"
                        ))
                    return models
        except Exception as e:
            print(f"火山引擎模型同步失败: {e}")
        
        return self._get_default_models()
    
    def _get_default_models(self) -> List[ModelInfo]:
        return [
            ModelInfo("doubao-pro-32k", "豆包 Pro 32K", "volcengine"),
            ModelInfo("doubao-lite-4k", "豆包 Lite 4K", "volcengine"),
        ]


class CustomModelAdapter(BaseModelSyncAdapter):
    """自定义供应商模型同步适配器"""
    
    async def fetch_models(self) -> List[ModelInfo]:
        # 自定义供应商，尝试通用方式获取
        url = f"{self.provider.endpoint}/v1/models"
        
        try:
            async with httpx.AsyncClient(timeout=30) as client:
                response = await client.get(url, headers=self.get_headers())
                
                if response.status_code == 200:
                    data = response.json()
                    models = []
                    for item in data.get("data", []):
                        models.append(ModelInfo(
                            model_id=item["id"],
                            name=item.get("id", ""),
                            owned_by=self.provider.type.value
                        ))
                    return models
        except Exception as e:
            print(f"自定义供应商模型同步失败: {e}")
        
        return []


# 适配器注册表
MODEL_SYNC_ADAPTERS = {
    "openai": OpenAIModelAdapter,
    "anthropic": AnthropicModelAdapter,
    "minimax": MinimaxModelAdapter,
    "deepseek": DeepseekModelAdapter,
    "azure": AzureModelAdapter,
    "volcengine": VolcengineModelAdapter,
    "custom": CustomModelAdapter,
    # 其他未列出的使用自定义适配器
}


class ModelSyncService:
    """模型同步服务"""
    
    def __init__(self, db: Session):
        self.db = db
    
    def get_adapter(self, provider: Provider) -> Optional[BaseModelSyncAdapter]:
        """获取对应的适配器"""
        adapter_class = MODEL_SYNC_ADAPTERS.get(provider.type.value)
        if adapter_class:
            return adapter_class(provider)
        # 未知的供应商类型使用自定义适配器
        return CustomModelAdapter(provider)
    
    async def sync_provider_models(self, provider: Provider) -> Dict[str, Any]:
        """
        同步单个供应商的模型列表
        返回: {"success": bool, "count": int, "models": list, "message": str}
        """
        adapter = self.get_adapter(provider)
        
        try:
            models = await adapter.fetch_models()
            
            # 更新Provider的models字段
            provider.models = json.dumps([m.to_dict() for m in models])
            provider.last_models_sync_at = datetime.now()
            
            self.db.commit()
            
            return {
                "success": True,
                "count": len(models),
                "models": [m.to_dict() for m in models],
                "message": f"成功同步 {len(models)} 个模型"
            }
        except Exception as e:
            self.db.rollback()
            return {
                "success": False,
                "count": 0,
                "models": [],
                "message": f"同步失败: {str(e)}"
            }
    
    async def sync_all_providers(self) -> Dict[str, Any]:
        """
        同步所有供应商的模型列表
        """
        providers = self.db.query(Provider).filter(
            Provider.status == "active"
        ).all()
        
        results = []
        success_count = 0
        fail_count = 0
        
        for provider in providers:
            result = await self.sync_provider_models(provider)
            results.append({
                "provider_id": provider.provider_id,
                "provider_name": provider.name,
                **result
            })
            if result["success"]:
                success_count += 1
            else:
                fail_count += 1
        
        return {
            "total": len(providers),
            "success": success_count,
            "failed": fail_count,
            "results": results
        }
    
    def get_provider_models(self, provider: Provider) -> List[ModelInfo]:
        """获取Provider已同步的模型列表"""
        if not provider.models:
            return []
        
        try:
            models_data = json.loads(provider.models)
            return [ModelInfo(**m) for m in models_data]
        except:
            return []


def create_model_sync_service(db: Session) -> ModelSyncService:
    """创建模型同步服务实例"""
    return ModelSyncService(db)


    async def auto_create_mappings(self, provider: Provider, auto_enable: bool = True) -> Dict[str, Any]:
        """
        自动创建模型映射
        参数:
            provider: 供应商
            auto_enable: 是否自动启用映射
        返回: {"created": int, "skipped": int, "errors": list}
        """
        from app.models.model_mapping import ModelMapping, ModelMappingStatus
        
        # 获取已同步的模型
        models = self.get_provider_models(provider)
        
        created = 0
        skipped = 0
        errors = []
        
        for model in models:
            try:
                # 检查是否已存在映射
                existing = self.db.query(ModelMapping).filter(
                    ModelMapping.provider_id == provider.provider_id,
                    ModelMapping.provider_model == model.model_id
                ).first()
                
                if existing:
                    skipped += 1
                    continue
                
                # 生成平台模型ID
                platform_model_id = f"{provider.type.value}-{model.model_id}"
                
                # 创建映射
                mapping = ModelMapping(
                    model_id=platform_model_id,
                    display_name=model.name,
                    provider_id=provider.provider_id,
                    provider_model=model.model_id,
                    status=ModelMappingStatus.active if auto_enable else ModelMappingStatus.disabled
                )
                
                self.db.add(mapping)
                created += 1
                
            except Exception as e:
                errors.append(f"{model.model_id}: {str(e)}")
        
        try:
            self.db.commit()
        except Exception as e:
            self.db.rollback()
            errors.append(f"Database commit error: {str(e)}")
        
        return {
            "created": created,
            "skipped": skipped,
            "errors": errors,
            "total": len(models)
        }


# 同步并自动创建映射的服务函数
async def sync_and_create_mappings(db: Session, provider: Provider, auto_enable: bool = True) -> Dict[str, Any]:
    """
    同步供应商模型并自动创建映射
    """
    service = ModelSyncService(db)
    
    # 1. 同步模型
    sync_result = await service.sync_provider_models(provider)
    
    if not sync_result["success"]:
        return {
            "sync_success": False,
            "mapping_created": 0,
            "message": sync_result["message"]
        }
    
    # 2. 自动创建映射
    mapping_result = await service.auto_create_mappings(provider, auto_enable)
    
    return {
        "sync_success": True,
        "sync_count": sync_result["count"],
        "mapping_created": mapping_result["created"],
        "mapping_skipped": mapping_result["skipped"],
        "mapping_errors": mapping_result["errors"],
        "message": f"同步 {sync_result['count']} 个模型，创建 {mapping_result['created']} 个映射"
    }
