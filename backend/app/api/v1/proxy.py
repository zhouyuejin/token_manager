"""
代理接口 - 核心中转功能

支持多渠道 Failover 和多 Key 轮询
"""
import json
import time
from typing import Optional, List
from pydantic import BaseModel
from fastapi import APIRouter, Depends, Request, HTTPException
from fastapi.responses import StreamingResponse
from sqlalchemy.orm import Session, selectinload

from app.core.database import get_db
from app.models.user import User
from app.models.api_key import ApiKey
from app.models.model import Model, ModelStatus
from app.models.channel import Channel, ChannelStatus
from app.models.model_group import ModelGroup, ModelGroupStatus
from app.services.proxy_service import ProxyService, create_proxy_service

router = APIRouter()


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


@router.get("/models")
async def list_models(request: Request, db: Session = Depends(get_db)):
    """
    OpenAI 风格可用模型列表。
    仅返回用户可访问的 active 模型。
    """
    user: User = getattr(request.state, "user", None)
    api_key: ApiKey = getattr(request.state, "api_key", None)

    if user is None or api_key is None:
        return {"object": "list", "data": []}

    proxy_service = create_proxy_service(db)
    effective_group_ids = proxy_service.get_effective_model_group_ids(user)

    if not effective_group_ids:
        return {"object": "list", "data": []}

    # 获取可访问的模型（需绑定 enabled channel）
    accessible_models = (
        db.query(Model)
        .join(Model.model_groups)
        .join(Model.model_channels)
        .join(Channel)
        .options(selectinload(Model.model_channels).selectinload(Channel))
        .filter(
            ModelGroup.group_id.in_(effective_group_ids),
            ModelGroup.status == ModelGroupStatus.active,
            Model.status == ModelStatus.active,
            ModelChannel.enabled == True,
            Channel.status == ChannelStatus.active,
        )
        .all()
    )

    models = [
        {
            "id": m.model_id,
            "object": "model",
            "owned_by": m.model_channels[0].channel_id if m.model_channels else "",
            "display_name": m.display_name,
        }
        for m in accessible_models
    ]
    return {"object": "list", "data": models}


@router.get("/balance")
async def get_balance(request: Request, db: Session = Depends(get_db)):
    """获取当前额度"""
    user: User = getattr(request.state, "user", None)
    
    if not user:
        raise HTTPException(status_code=401, detail="无效的API Key")
    
    quota_remain = user.quota - user.quota_used
    return {"balance": quota_remain}


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
    
    # 1. 检查模型分组访问权限 (GC-1)
    group_check = proxy_service.check_model_group_access(api_key, user, chat_request.model)
    if not group_check["allowed"]:
        raise HTTPException(status_code=403, detail=group_check["message"])

    # 2. 检查额度
    estimated_tokens = 1000
    quota_check = proxy_service.check_quota(user, api_key, estimated_tokens)
    if not quota_check["allowed"]:
        raise HTTPException(status_code=403, detail=quota_check["message"])
    
    # 3. 构建请求数据
    request_data = chat_request.model_dump(exclude={"stream"})
    request_data = {k: v for k, v in request_data.items() if v is not None}
    
    # 4. 转发请求（带 failover）
    if chat_request.stream:
        # 流式响应
        stream_gen = proxy_service.forward_stream(chat_request.model, user, api_key, request_data)
        
        _user_id = user.user_id
        _key_id = api_key.key_id
        _model = chat_request.model
        
        def sync_generator():
            from app.core.database import SessionLocal
            db = SessionLocal()
            try:
                completion_text = ""
                for chunk in stream_gen:
                    line = chunk.strip()
                    if line.startswith("data: "):
                        data_str = line[6:]
                        if data_str and data_str != "[DONE]":
                            try:
                                data = json.loads(data_str)
                                choices = data.get("choices", [])
                                if choices:
                                    delta = choices[0].get("delta", {})
                                    content = delta.get("content", "")
                                    if content:
                                        completion_text += content
                            except (json.JSONDecodeError, KeyError, TypeError):
                                pass
                    yield chunk
            finally:
                # 流结束时记录并扣减
                try:
                    service = create_proxy_service(db)
                    tokens = {
                        "prompt_tokens": 0,
                        "completion_tokens": len(completion_text) // 4,
                        "total_tokens": len(completion_text) // 4
                    }
                    service.record_usage(
                        user_id=_user_id,
                        key_id=_key_id,
                        channel_id=None,
                        model=_model,
                        tokens=tokens,
                        latency_ms=0,
                        status_code=200,
                        error_message=None
                    )
                    import asyncio
                    user_obj = db.query(User).filter(User.user_id == _user_id).first()
                    api_key_obj = db.query(ApiKey).filter(ApiKey.key_id == _key_id).first()
                    if user_obj and api_key_obj:
                        asyncio.run(service.deduct_quota(user_obj, api_key_obj, tokens))
                except Exception:
                    pass
                finally:
                    db.close()
        
        return StreamingResponse(sync_generator(), media_type="text/event-stream")
    else:
        # 普通响应
        result = proxy_service.forward_with_failover(chat_request.model, user, api_key, request_data)
        
        # 5. 记录用量并扣减
        tokens = proxy_service.calculate_tokens(
            request_data,
            result.get("data") if result.get("success") else None
        )
        
        if result.get("success") and result.get("status_code") == 200:
            proxy_service.record_usage(
                user_id=user.user_id,
                key_id=api_key.key_id,
                channel_id=result.get("channel_id"),
                model=chat_request.model,
                tokens=tokens,
                latency_ms=result.get("latency_ms", 0),
                status_code=result.get("status_code", 200),
                error_message=result.get("error")
            )
            await proxy_service.deduct_quota(user, api_key, tokens)
            return result.get("data", {})
        else:
            proxy_service.record_usage(
                user_id=user.user_id,
                key_id=api_key.key_id,
                channel_id=result.get("channel_id"),
                model=chat_request.model,
                tokens=tokens,
                latency_ms=result.get("latency_ms", 0),
                status_code=result.get("status_code", 500),
                error_message=result.get("error")
            )
            raise HTTPException(
                status_code=result.get("status_code", 500),
                detail=result.get("error", "请求失败")
            )


# ========== v1 前缀路由 ==========

v1_router = APIRouter()

@v1_router.get("/models")
async def v1_list_models(request: Request, db: Session = Depends(get_db)):
    return await list_models(request, db)

@v1_router.get("/balance")
async def v1_get_balance(request: Request, db: Session = Depends(get_db)):
    return await get_balance(request, db)

@v1_router.post("/chat/completions")
async def v1_chat_completions(
    request: Request,
    chat_request: ChatCompletionRequest,
    db: Session = Depends(get_db)
):
    return await chat_completions(request, chat_request, db)
