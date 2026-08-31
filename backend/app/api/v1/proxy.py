"""
代理接口 - 核心中转功能
"""
import json
from typing import Optional, List, Union
from fastapi import APIRouter, Depends, Request, HTTPException
from fastapi.responses import StreamingResponse
from sqlalchemy.orm import Session
from pydantic import BaseModel

from app.core.database import get_db
from app.models.user import User
from app.models.api_key import ApiKey
from app.models.model_mapping import ModelMapping
from app.services.proxy_service import ProxyService, create_proxy_service

router = APIRouter()


# ========== Request Models ==========

class ChatMessage(BaseModel):
    """聊天消息"""
    role: str
    content: str


class ChatCompletionRequest(BaseModel):
    """ChatCompletion请求"""
    model: str
    messages: List[ChatMessage]
    temperature: Optional[float] = 0.7
    max_tokens: Optional[int] = 1000
    stream: Optional[bool] = False
    top_p: Optional[float] = 1.0
    frequency_penalty: Optional[float] = 0.0
    presence_penalty: Optional[float] = 0.0


# ========== API Endpoints ==========

@router.get("/models")
async def list_models(request: Request, db: Session = Depends(get_db)):
    """
    获取可用模型列表
    根据API Key关联的模型分组过滤模型
    """
    # 获取当前请求的用户和API Key
    user: User = getattr(request.state, "user", None)
    api_key: ApiKey = getattr(request.state, "api_key", None)
    
    # 如果没有API Key，返回所有启用的模型
    if not api_key:
        mappings = db.query(ModelMapping).filter(
            ModelMapping.status == "active"
        ).all()
    else:
        # 获取API Key关联的模型分组
        key_groups = api_key.model_groups
        
        if not key_groups:
            # 没有关联分组，返回所有启用的模型（兼容旧Key）
            mappings = db.query(ModelMapping).filter(
                ModelMapping.status == "active"
            ).all()
        else:
            # 获取分组关联的供应商
            from app.models.model_group import ModelGroup
            from app.models.provider import Provider
            
            group_ids = [g.group_id for g in key_groups]
            groups = db.query(ModelGroup).filter(
                ModelGroup.group_id.in_(group_ids)
            ).all()
            
            # 获取分组关联的供应商ID
            provider_ids = set()
            for group in groups:
                for provider in group.providers:
                    provider_ids.add(provider.provider_id)
            
            # 只返回这些供应商的模型映射
            if provider_ids:
                mappings = db.query(ModelMapping).filter(
                    ModelMapping.status == "active",
                    ModelMapping.provider_id.in_(list(provider_ids))
                ).all()
            else:
                mappings = []
    
    models = [
        {
            "id": mapping.model_id,
            "object": "model",
            "owned_by": mapping.provider_id,
            "display_name": mapping.display_name,
            "provider_model": mapping.provider_model
        }
        for mapping in mappings
    ]
    
    # 如果没有映射，返回默认模型
    if not models:
        models = [
            {"id": "gpt-4", "object": "model", "owned_by": "openai"},
            {"id": "gpt-3.5-turbo", "object": "model", "owned_by": "openai"},
        ]
    
    return {"object": "list", "data": models}


@router.get("/balance")
async def get_balance(request: Request, db: Session = Depends(get_db)):
    """
    获取当前额度
    """
    user: User = getattr(request.state, "user", None)
    api_key: ApiKey = getattr(request.state, "api_key", None)
    
    if not user or not api_key:
        raise HTTPException(status_code=401, detail="无效的API Key")
    
    # 计算剩余额度
    quota_remain = user.quota - user.quota_used
    
    return {
        "balance": quota_remain,
        "daily_used": api_key.daily_used,
        "daily_limit": api_key.daily_limit,
        "monthly_used": api_key.monthly_used,
        "monthly_limit": api_key.monthly_limit
    }


@router.post("/chat/completions")
async def chat_completions(
    request: Request,
    chat_request: ChatCompletionRequest,
    db: Session = Depends(get_db)
):
    """
    大模型API中转接口
    兼容OpenAI格式
    """
    user: User = getattr(request.state, "user", None)
    api_key: ApiKey = getattr(request.state, "api_key", None)
    
    if not user or not api_key:
        raise HTTPException(status_code=401, detail="无效的API Key")
    
    proxy_service = create_proxy_service(db)
    
    # 1. 获取模型映射
    model_mapping = proxy_service.get_model_mapping(chat_request.model)
    if not model_mapping:
        raise HTTPException(status_code=400, detail=f"不支持的模型: {chat_request.model}")
    
    # 2. 获取供应商
    provider = proxy_service.get_provider(model_mapping.provider_id)
    if not provider:
        raise HTTPException(status_code=500, detail="供应商不可用")
    
    # 3. 检查额度
    # 估算token数量（简化处理）
    estimated_tokens = 1000
    quota_check = proxy_service.check_quota(user, api_key, estimated_tokens)
    if not quota_check["allowed"]:
        raise HTTPException(status_code=403, detail=quota_check["message"])
    
    # 4. 构建请求数据
    request_data = chat_request.model_dump(exclude={"stream"})
    # 移除None值
    request_data = {k: v for k, v in request_data.items() if v is not None}
    
    # 5. 转发请求
    if chat_request.stream:
        # 流式响应
        return StreamingResponse(
            proxy_service.forward_stream_request(provider, model_mapping, request_data),
            media_type="text/event-stream"
        )
    else:
        # 普通响应
        result = proxy_service.forward_request(provider, model_mapping, request_data)
        
        # 6. 计算token数量
        tokens = proxy_service.calculate_tokens(
            request_data,
            result["data"] if result["success"] else None
        )
        
        # 7. 记录用量
        proxy_service.record_usage(
            user_id=user.user_id,
            key_id=api_key.key_id,
            provider_id=provider.provider_id,
            model=chat_request.model,
            tokens=tokens,
            latency_ms=result["latency_ms"],
            status_code=result["status_code"],
            error_message=result["error"]
        )
        
        # 8. 如果成功，扣减额度
        if result["success"] and result["status_code"] == 200:
            proxy_service.deduct_quota(user, api_key, tokens)
        
        # 9. 返回响应
        if not result["success"]:
            raise HTTPException(
                status_code=result["status_code"],
                detail=result["error"]
            )
        
        return result["data"]


# ========== 兼容OpenAI的v1前缀路由 ==========

v1_router = APIRouter()


@v1_router.get("/models")
async def v1_list_models(db: Session = Depends(get_db)):
    """v1模型列表"""
    return await list_models(db)


@v1_router.get("/balance")
async def v1_get_balance(request: Request, db: Session = Depends(get_db)):
    """v1额度查询"""
    return await get_balance(request, db)


@v1_router.post("/chat/completions")
async def v1_chat_completions(
    request: Request,
    chat_request: ChatCompletionRequest,
    db: Session = Depends(get_db)
):
    """v1聊天完成"""
    return await chat_completions(request, chat_request, db)
