"""
代理接口 - 核心中转功能
"""
import json
import time
from typing import Optional, List, Union
from fastapi import APIRouter, Depends, Request, HTTPException
from fastapi.responses import StreamingResponse
from sqlalchemy.orm import Session
from pydantic import BaseModel

from app.core.database import get_db
from app.models.user import User
from app.models.api_key import ApiKey
from app.models.model_group import ModelGroup, ModelGroupStatus
from sqlalchemy.orm import selectinload
from app.models.model_mapping import ModelMapping, ModelMappingStatus
from app.models.provider import Provider, ProviderStatus
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
    OpenAI 风格可用模型列表（§13 Task 4）。

    仅返回用户可访问的 active 模型（绑定到用户有效 active 分组中、供应商 active）。
    无权限时返回空列表 —— 删除 fake gpt-4 / gpt-3.5-turbo fallback。
    列表与 check_model_group_access 判定一致。
    """
    user: User = getattr(request.state, "user", None)
    api_key: ApiKey = getattr(request.state, "api_key", None)

    if user is None or api_key is None:
        return {"object": "list", "data": []}

    proxy_service = create_proxy_service(db)
    effective_group_ids = proxy_service.get_effective_model_group_ids(user)

    if not effective_group_ids:
        return {"object": "list", "data": []}

    accessible_models = (
        db.query(ModelMapping)
        .join(ModelMapping.model_groups)
        .options(selectinload(ModelMapping.provider))
        .filter(
            ModelGroup.group_id.in_(effective_group_ids),
            ModelGroup.status == ModelGroupStatus.active,
            ModelMapping.status == ModelMappingStatus.active,
        )
        .all()
    )
    accessible = [m for m in accessible_models if m.provider and m.provider.status == ProviderStatus.active]

    models = [
        {
            "id": m.model_id,
            "object": "model",
            "owned_by": m.provider_id,
            "display_name": m.display_name,
            "provider_model": m.provider_model,
        }
        for m in accessible
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
    
    # 3. 检查该模型是否在供应商的 models 列表中（如果配置了的话）
    if provider.models:
        try:
            provider_models = json.loads(provider.models) if isinstance(provider.models, str) else provider.models
            provider_model_ids = [m.get('model_id') for m in provider_models if isinstance(m, dict)]
            if model_mapping.model_id not in provider_model_ids:
                raise HTTPException(status_code=403, detail=f"该模型未在此供应商上启用")
        except:
            pass  # 如果解析失败，跳过检查
    
    # 4. 检查模型分组访问权限 (GC-1: single gate)
    group_check = proxy_service.check_model_group_access(api_key, user, chat_request.model)
    if not group_check["allowed"]:
        raise HTTPException(status_code=403, detail=group_check["message"])

    # 5. 检查额度
    estimated_tokens = 1000
    quota_check = proxy_service.check_quota(user, api_key, estimated_tokens)
    if not quota_check["allowed"]:
        raise HTTPException(status_code=403, detail=quota_check["message"])
    
    # 6. 构建请求数据
    request_data = chat_request.model_dump(exclude={"stream"})
    # 移除None值
    request_data = {k: v for k, v in request_data.items() if v is not None}
    
    # 7. 转发请求
    if chat_request.stream:
        # 流式响应 - 使用包装器追踪延迟
        stream_generator, start_time = proxy_service.forward_stream_request(provider, model_mapping, request_data)
        
        # 保存用户信息用于延迟记录
        _user_id = user.user_id
        _key_id = api_key.key_id
        _provider_id = provider.provider_id
        _model = chat_request.model
        
        def sync_generator():
            """同步generator，用于在StreamingResponse中迭代"""
            from app.core.database import SessionLocal
            db = SessionLocal()
            try:
                for chunk in stream_generator:
                    yield chunk
            finally:
                # 流结束时记录延迟（使用新的数据库会话）
                latency_ms = int((time.time() - start_time) * 1000)
                try:
                    service = create_proxy_service(db)
                    service.record_usage(
                        user_id=_user_id,
                        key_id=_key_id,
                        provider_id=_provider_id,
                        model=_model,
                        tokens={"prompt_tokens": 0, "completion_tokens": 0, "total_tokens": 0},
                        latency_ms=latency_ms,
                        status_code=200,
                        error_message=None
                    )
                finally:
                    db.close()
        
        return StreamingResponse(
            sync_generator(),
            media_type="text/event-stream"
        )
    else:
        # 普通响应
        result = proxy_service.forward_request(provider, model_mapping, request_data)
        
        # 8. 计算token数量
        tokens = proxy_service.calculate_tokens(
            request_data,
            result["data"] if result["success"] else None
        )
        
        # 9. 记录用量
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
        
        # 10. 如果成功，扣减额度
        if result["success"] and result["status_code"] == 200:
            await proxy_service.deduct_quota(user, api_key, tokens)
        
        # 11. 返回响应
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
