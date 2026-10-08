"""
代理接口 - 核心中转功能

支持多渠道 Failover 和多 Key 轮询
"""
import json
import time
import math
import logging
from typing import Optional, List
from pydantic import BaseModel
from fastapi import APIRouter, Depends, Request, HTTPException
from fastapi.responses import Response
from app.api.streaming import QuotaStreamingResponse
from app.services.quota_reservation_service import estimate_request
from sqlalchemy.orm import Session, selectinload

from app.core.database import get_db
from app.models.user import User
from app.models.api_key import ApiKey
from app.models.model import Model, ModelStatus
from app.models.channel import Channel, ChannelStatus
from app.models.model_channel import ModelChannel
from app.models.model_group import ModelGroup, ModelGroupStatus
from app.services.proxy_service import ProxyService, create_proxy_service
from app.services.conversation_gateway import proxy_conversation
from app.services.api_key_freeze_service import record_api_key_error
from app.services.rate_limit_service import (
    check_proxy_rate_limit,
    get_rate_limit_redis_client,
    release_proxy_concurrency,
)

logger = logging.getLogger(__name__)
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
    max_tokens: Optional[int] = None
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
        .options(selectinload(Model.model_channels).selectinload(ModelChannel.channel))
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
    request_id = request.state.request_id
    
    # 1. 检查模型分组访问权限 (GC-1)
    group_check = proxy_service.check_model_group_access(api_key, user, chat_request.model)
    if not group_check["allowed"]:
        raise HTTPException(status_code=403, detail=group_check["message"])

    # 限流和预扣采用同一份请求及保守估算。
    request_data = chat_request.model_dump(exclude={"stream"})
    request_data = {k: v for k, v in request_data.items() if v is not None}
    estimated_tokens = sum(estimate_request(request_data))

    rate_limit_redis = get_rate_limit_redis_client()
    rate_limit = check_proxy_rate_limit(rate_limit_redis, api_key, user, chat_request.model, estimated_tokens)
    concurrency_key = rate_limit.get("concurrency_key")
    if not rate_limit["allowed"]:
        record_api_key_error(db, api_key, "rate_limit")
        retry_after_ms = rate_limit.get("retry_after_ms", 1000)
        raise HTTPException(
            status_code=429,
            detail=rate_limit.get("detail") or "请求过于频繁",
            headers={"Retry-After": str(max(1, math.ceil(retry_after_ms / 1000)))},
        )
    
    try:
        proxy_service.reserve_quota(user, api_key, chat_request.model, request_data)
    except BaseException:
        release_proxy_concurrency(rate_limit_redis, concurrency_key)
        raise
    
    # 4. 转发请求（带 failover）
    if chat_request.stream:
        # 流式响应
        _user_id = user.user_id
        _key_id = api_key.key_id
        _model = chat_request.model
        try:
            stream_gen = proxy_service.forward_stream(chat_request.model, user, api_key, request_data, request_id=request_id)
        except BaseException:
            proxy_service.release_reservation()
            release_proxy_concurrency(rate_limit_redis, concurrency_key)
            raise
        
        _concurrency_key = concurrency_key
        _rate_limit_redis = rate_limit_redis
        _reservation_id = proxy_service.reservation_id
        
        def sync_generator():
            from app.core.database import SessionLocal
            db = SessionLocal()
            done = False
            settlement_error = None
            try:
                completion_text = ""
                for chunk in stream_gen:
                    line = chunk.strip()
                    if line == 'data: [DONE]':
                        done = True
                        continue  # 结算完成后才向客户端发终止标记。
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
                    service.reservation_id = _reservation_id
                    metadata = proxy_service.stream_metadata
                    succeeded = metadata.get('status_code') == 200 and metadata.get('completed')
                    tokens = (metadata.get('tokens') or proxy_service.calculate_tokens(request_data, {'choices': [{'message': {'content': completion_text}}]})) if succeeded else {}
                    if not metadata.get('recorded'):
                        service.record_usage(
                            user_id=_user_id,
                            key_id=_key_id,
                            channel_id=metadata.get("channel_id"),
                            model=_model,
                            tokens=tokens,
                            latency_ms=metadata.get("latency_ms", 0),
                            status_code=200 if succeeded else (metadata.get("status_code") if metadata.get("status_code") != 200 else 499),
                            error_message=metadata.get("error") or (None if succeeded else "流式请求未完成"),
                            attribution=proxy_service.usage_attribution[_key_id],
                            request_content=request_data,
                            response_content={"choices": [{"message": {"content": completion_text}}]},
                        )
                        import asyncio
                        user_obj = db.query(User).filter(User.user_id == _user_id).first()
                        api_key_obj = db.query(ApiKey).filter(ApiKey.key_id == _key_id).first()
                        if user_obj and api_key_obj and succeeded:
                            asyncio.run(service.deduct_quota(user_obj, api_key_obj, tokens))
                        else:
                            db.commit()
                except Exception:
                    db.rollback()
                    settlement_error = '流式结算失败，预扣将释放，请联系管理员检查渠道用量'
                    logger.exception("流式用量归因记录失败，key_id=%s", _key_id)
                finally:
                    try:
                        stream_gen.close()
                    finally:
                        db.close()
            if settlement_error:
                yield 'data: ' + json.dumps({'error': settlement_error}, ensure_ascii=False) + '\n\n'
            if done:
                yield 'data: [DONE]\n\n'
        
        return QuotaStreamingResponse(
            sync_generator(), db.get_bind(), _reservation_id,
            on_close=lambda: release_proxy_concurrency(_rate_limit_redis, _concurrency_key))
    else:
        # 普通响应
        try:
            result = proxy_service.forward_with_failover(chat_request.model, user, api_key, request_data, request_id=request_id)
            
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
                    error_message=result.get("error"),
                    request_content=request_data,
                    response_content=result.get("data") if result.get("success") else None,
                )
                await proxy_service.deduct_quota(user, api_key, tokens)
                return result.get("data", {})
            else:
                if not result.get("usage_recorded"):
                    proxy_service.record_usage(
                        user_id=user.user_id,
                        key_id=api_key.key_id,
                        channel_id=result.get("channel_id"),
                        model=chat_request.model,
                        tokens=tokens,
                        latency_ms=result.get("latency_ms", 0),
                        status_code=result.get("status_code", 500),
                        error_message=result.get("error"),
                        request_content=request_data,
                    )
                db.commit()
                raise HTTPException(
                    status_code=result.get("status_code", 500),
                    detail=result.get("error", "请求失败")
                )
        finally:
            try:
                proxy_service.release_reservation()
            finally:
                release_proxy_concurrency(rate_limit_redis, concurrency_key)


# ========== v1 前缀路由 ==========

v1_router = APIRouter()


async def _proxy_protocol(request: Request, db: Session, path: str, api_type: str, multipart: bool = False):
    user: User = getattr(request.state, "user", None)
    api_key: ApiKey = getattr(request.state, "api_key", None)
    if not user or not api_key:
        raise HTTPException(status_code=401, detail="无效的API Key")

    content_type = request.headers.get("content-type", "application/json")
    if multipart:
        form = await request.form()
        fields, files = {}, []
        for key, value in form.multi_items():
            if hasattr(value, "read"):
                files.append((key, (value.filename, await value.read(), value.content_type)))
            else:
                fields[key] = str(value)
        model = fields.get("model")
        body = (fields, files)
        audit_request = fields
        request_data = {"max_tokens": 1024}
    else:
        try:
            body = await request.json()
        except ValueError as exc:
            raise HTTPException(status_code=400, detail="请求体必须是 JSON") from exc
        if not isinstance(body, dict):
            raise HTTPException(status_code=400, detail="请求体必须是 JSON 对象")
        model = body.get("model")
        audit_request = body
        request_data = {**body, "max_tokens": body.get("max_tokens") or 1024}
    if not isinstance(model, str) or not model:
        raise HTTPException(status_code=422, detail="缺少 model")

    service = create_proxy_service(db)
    group_check = service.check_model_group_access(api_key, user, model)
    if not group_check["allowed"]:
        raise HTTPException(status_code=403, detail=group_check["message"])
    estimated_tokens = sum(estimate_request(request_data))
    rate_limit_redis = get_rate_limit_redis_client()
    rate_limit = check_proxy_rate_limit(rate_limit_redis, api_key, user, model, estimated_tokens)
    concurrency_key = rate_limit.get("concurrency_key")
    if not rate_limit["allowed"]:
        record_api_key_error(db, api_key, "rate_limit")
        retry_after_ms = rate_limit.get("retry_after_ms", 1000)
        raise HTTPException(
            status_code=429,
            detail=rate_limit.get("detail") or "请求过于频繁",
            headers={"Retry-After": str(max(1, math.ceil(retry_after_ms / 1000)))},
        )
    try:
        service.reserve_quota(user, api_key, model, request_data)
        result = service.forward_protocol_with_failover(
            model, user, api_key, api_type, path, body, content_type,
        )
        if result.get("usage_recorded"):
            raise HTTPException(status_code=result.get("status_code", 502), detail=result.get("error", "请求失败"))

        response_data = None
        try:
            response_data = json.loads(result.get("body", b"{}"))
        except (ValueError, TypeError):
            pass
        usage_data = response_data.get("usage") if isinstance(response_data, dict) else None
        if isinstance(usage_data, dict):
            usage_data = {
                "prompt_tokens": usage_data.get("prompt_tokens", usage_data.get("input_tokens", 0)),
                "completion_tokens": usage_data.get("completion_tokens", usage_data.get("output_tokens", 0)),
                "total_tokens": usage_data.get("total_tokens"),
            }
            if usage_data["total_tokens"] is None:
                usage_data["total_tokens"] = usage_data["prompt_tokens"] + usage_data["completion_tokens"]
            tokens = service.calculate_tokens({"max_tokens": 0}, {"usage": usage_data})
        else:
            tokens = {"prompt_tokens": 0, "completion_tokens": 0, "total_tokens": 0}

        status_code = result.get("status_code", 502)
        service.record_usage(
            user.user_id, api_key.key_id, result.get("channel_id"), model, tokens,
            result.get("latency_ms", 0), status_code, result.get("error"),
            api_type=api_type,
            request_content=audit_request,
            response_content=response_data if result.get("success") else None,
        )
        if result.get("success"):
            await service.deduct_quota(user, api_key, tokens)
        else:
            db.commit()
            raise HTTPException(status_code=status_code, detail=result.get("error", "请求失败"))
        return Response(content=result.get("body", b""), status_code=status_code,
                        media_type=result.get("content_type", "application/json"))
    finally:
        try:
            service.release_reservation()
        finally:
            release_proxy_concurrency(rate_limit_redis, concurrency_key)


async def responses(request: Request, db: Session = Depends(get_db)):
    return await proxy_conversation(request, db, "responses")


async def embeddings(request: Request, db: Session = Depends(get_db)):
    return await _proxy_protocol(request, db, "embeddings", "embeddings")


async def image_generations(request: Request, db: Session = Depends(get_db)):
    return await _proxy_protocol(request, db, "images/generations", "images")


async def image_edits(request: Request, db: Session = Depends(get_db)):
    return await _proxy_protocol(request, db, "images/edits", "images", multipart=True)


async def image_variations(request: Request, db: Session = Depends(get_db)):
    return await _proxy_protocol(request, db, "images/variations", "images", multipart=True)


async def audio_transcriptions(request: Request, db: Session = Depends(get_db)):
    return await _proxy_protocol(request, db, "audio/transcriptions", "audio/transcriptions", multipart=True)


for protocol_path, handler in (
    ("/responses", responses), ("/embeddings", embeddings),
    ("/images/generations", image_generations), ("/images/edits", image_edits),
    ("/images/variations", image_variations),
    ("/audio/transcriptions", audio_transcriptions),
):
    router.add_api_route(protocol_path, handler, methods=["POST"])
    v1_router.add_api_route(protocol_path, handler, methods=["POST"])

@v1_router.get("/models")
async def v1_list_models(request: Request, db: Session = Depends(get_db)):
    return await list_models(request, db)

@v1_router.get("/balance")
async def v1_get_balance(request: Request, db: Session = Depends(get_db)):
    return await get_balance(request, db)

@v1_router.post("/chat/completions")
async def v1_chat_completions(
    request: Request,
    db: Session = Depends(get_db)
):
    return await proxy_conversation(request, db, "chat")


@v1_router.post("/messages")
async def v1_messages(request: Request, db: Session = Depends(get_db)):
    return await proxy_conversation(request, db, "anthropic")


router.add_api_route("/messages", v1_messages, methods=["POST"])
