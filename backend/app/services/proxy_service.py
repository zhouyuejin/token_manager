"""
代理服务 - 核心中转功能
"""
import json
import time
import secrets
from datetime import datetime
from typing import Optional, Dict, Any, List
import httpx
from sqlalchemy.orm import Session

from app.models.user import User
from app.models.api_key import ApiKey
from app.models.provider import Provider
from app.models.model_mapping import ModelMapping
from app.models.usage_log import UsageLog


class ProxyService:
    """代理服务类"""
    
    def __init__(self, db: Session):
        self.db = db
    
    def verify_api_key(self, api_key: str) -> Optional[ApiKey]:
        """验证API Key"""
        key = self.db.query(ApiKey).filter(
            ApiKey.api_key == api_key,
            ApiKey.status == "active"
        ).first()
        return key
    
    def get_user_from_key(self, api_key: ApiKey) -> Optional[User]:
        """从API Key获取用户"""
        user = self.db.query(User).filter(
            User.user_id == api_key.user_id,
            User.status == "active"
        ).first()
        return user
    
    def check_quota(self, user: User, api_key: ApiKey, estimated_tokens: int = 1000) -> Dict[str, Any]:
        """检查额度是否充足"""
        # 检查用户额度
        quota_remain = user.quota - user.quota_used
        if quota_remain < estimated_tokens:
            return {
                "allowed": False,
                "reason": "quota_insufficient",
                "message": "用户额度不足"
            }
        
        # 检查API Key日限额
        if api_key.daily_limit > 0 and api_key.daily_used + estimated_tokens > api_key.daily_limit:
            return {
                "allowed": False,
                "reason": "daily_limit_exceeded",
                "message": "日限额已用完"
            }
        
        # 检查API Key月限额
        if api_key.monthly_limit > 0 and api_key.monthly_used + estimated_tokens > api_key.monthly_limit:
            return {
                "allowed": False,
                "reason": "monthly_limit_exceeded",
                "message": "月限额已用完"
            }
        
        return {"allowed": True}
    
    def get_model_mapping(self, model_id: str) -> Optional[ModelMapping]:
        """获取模型映射"""
        # 先精确匹配
        mapping = self.db.query(ModelMapping).filter(
            ModelMapping.model_id == model_id,
            ModelMapping.status == "active"
        ).first()
        
        if mapping:
            return mapping
        
        # 再匹配别名
        mappings = self.db.query(ModelMapping).filter(
            ModelMapping.status == "active"
        ).all()
        
        for m in mappings:
            aliases = m.aliases
            if aliases:
                try:
                    alias_list = json.loads(aliases) if isinstance(aliases, str) else aliases
                    if model_id in alias_list:
                        return m
                except:
                    pass
        
        return None
    
    def get_provider(self, provider_id: str) -> Optional[Provider]:
        """获取供应商"""
        return self.db.query(Provider).filter(
            Provider.provider_id == provider_id,
            Provider.status == "active"
        ).first()
    
    def get_default_provider(self) -> Optional[Provider]:
        """获取默认供应商（优先级最高的）"""
        return self.db.query(Provider).filter(
            Provider.status == "active"
        ).order_by(Provider.priority.asc()).first()
    
    def forward_request(
        self,
        provider: Provider,
        model_mapping: ModelMapping,
        request_data: Dict[str, Any]
    ) -> Dict[str, Any]:
        """转发请求到上游供应商"""
        start_time = time.time()
        
        # 构建上游请求
        upstream_url = f"{provider.endpoint.rstrip('/')}/chat/completions"
        
        # 转换模型名
        request_data["model"] = model_mapping.provider_model
        
        # 构建请求头
        headers = {
            "Authorization": f"Bearer {provider.api_key}",
            "Content-Type": "application/json"
        }
        
        # 添加供应商特定的请求头
        if provider.type.value == "azure":
            headers["api-key"] = provider.api_key
            # Azure需要不同的认证方式
        
        try:
            with httpx.Client(timeout=provider.timeout) as client:
                response = client.post(
                    upstream_url,
                    json=request_data,
                    headers=headers
                )
                
                latency_ms = int((time.time() - start_time) * 1000)
                
                return {
                    "success": True,
                    "status_code": response.status_code,
                    "data": response.json() if response.text else {},
                    "latency_ms": latency_ms,
                    "error": None
                }
                
        except httpx.TimeoutException:
            latency_ms = int((time.time() - start_time) * 1000)
            return {
                "success": False,
                "status_code": 504,
                "data": {},
                "latency_ms": latency_ms,
                "error": "上游请求超时"
            }
        except Exception as e:
            latency_ms = int((time.time() - start_time) * 1000)
            return {
                "success": False,
                "status_code": 500,
                "data": {},
                "latency_ms": latency_ms,
                "error": str(e)
            }
    
    def forward_stream_request(
        self,
        provider: Provider,
        model_mapping: ModelMapping,
        request_data: Dict[str, Any]
    ):
        """转发流式请求到上游供应商"""
        # 构建上游请求
        upstream_url = f"{provider.endpoint.rstrip('/')}/chat/completions"
        
        # 转换模型名
        request_data["model"] = model_mapping.provider_model
        
        # 构建请求头
        headers = {
            "Authorization": f"Bearer {provider.api_key}",
            "Content-Type": "application/json"
        }
        
        try:
            with httpx.Client(timeout=provider.timeout) as client:
                with client.stream("POST", upstream_url, json=request_data, headers=headers) as response:
                    for chunk in response.iter_lines():
                        if chunk:
                            yield chunk
                            
        except Exception as e:
            yield f'data: {{"error": "{str(e)}"}}\n\n'
    
    def calculate_tokens(self, request_data: Dict[str, Any], response_data: Optional[Dict[str, Any]] = None) -> Dict[str, int]:
        """计算Token数量（估算）"""
        # 简单的估算方法
        # 实际应该使用tiktoken等库精确计算
        
        prompt_tokens = 0
        completion_tokens = 0
        
        if "messages" in request_data:
            for msg in request_data["messages"]:
                if "content" in msg:
                    # 简单估算：字符数/4
                    prompt_tokens += len(msg["content"]) // 4
        
        if response_data and "choices" in response_data:
            for choice in response_data["choices"]:
                if "message" in choice and "content" in choice["message"]:
                    completion_tokens += len(choice["message"]["content"]) // 4
        
        return {
            "prompt_tokens": prompt_tokens,
            "completion_tokens": completion_tokens,
            "total_tokens": prompt_tokens + completion_tokens
        }
    
    def record_usage(
        self,
        user_id: str,
        key_id: str,
        provider_id: str,
        model: str,
        tokens: Dict[str, int],
        latency_ms: int,
        status_code: int,
        error_message: Optional[str] = None
    ):
        """记录用量日志"""
        log_id = f"log_{secrets.token_hex(8)}"
        
        usage_log = UsageLog(
            log_id=log_id,
            user_id=user_id,
            key_id=key_id,
            provider_id=provider_id,
            model=model,
            prompt_tokens=tokens.get("prompt_tokens", 0),
            completion_tokens=tokens.get("completion_tokens", 0),
            total_tokens=tokens.get("total_tokens", 0),
            latency_ms=latency_ms,
            status_code=status_code,
            error_message=error_message
        )
        
        self.db.add(usage_log)
    
    def deduct_quota(
        self,
        user: User,
        api_key: ApiKey,
        tokens: Dict[str, int]
    ):
        """扣减额度"""
        total_tokens = tokens.get("total_tokens", 0)
        
        # 扣减用户额度
        user.quota_used += total_tokens
        
        # 扣减API Key日用量
        api_key.daily_used += total_tokens
        
        # 扣减API Key月用量
        api_key.monthly_used += total_tokens
        
        # 更新最后使用时间
        api_key.last_used_at = datetime.now()
        
        self.db.commit()


def create_proxy_service(db: Session) -> ProxyService:
    """创建代理服务实例"""
    return ProxyService(db)
