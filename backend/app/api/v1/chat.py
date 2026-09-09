"""
Chat API - 对话管理接口
"""
import json
import secrets
from typing import Optional, List, Any
from fastapi import APIRouter, Depends, HTTPException, status, Request
from fastapi.responses import StreamingResponse
from sqlalchemy.orm import Session
from pydantic import BaseModel

from app.core.database import get_db
from app.models.user import User
from app.models.api_key import ApiKey, ApiKeyStatus
from app.models.chat import ChatConversation, ChatMessage, MessageRole
from app.dependencies import get_current_user
from app.services.proxy_service import create_proxy_service

router = APIRouter()


class ChatConversationCreate(BaseModel):
    title: Optional[str] = None
    model: str
    channel_id: Optional[str] = None  # 改为 channel_id
    system_prompt: Optional[str] = None


class ChatConversationUpdate(BaseModel):
    title: Optional[str] = None
    model: Optional[str] = None
    channel_id: Optional[str] = None
    system_prompt: Optional[str] = None


class ChatConversationResponse(BaseModel):
    conversation_id: str
    user_id: str
    title: Optional[str] = None
    channel_id: Optional[str] = None
    model_id: str
    system_prompt: Optional[str] = None
    created_at: Any
    updated_at: Any
    message_count: int = 0


class ChatConversationListResponse(BaseModel):
    total: int
    items: List[ChatConversationResponse]


class ChatMessageResponse(BaseModel):
    message_id: str
    conversation_id: str
    role: str
    content: str
    model: str
    tokens: Optional[int] = 0
    created_at: Any


class ChatMessageListResponse(BaseModel):
    total: int
    items: List[ChatMessageResponse]


class MessageItem(BaseModel):
    role: str
    content: str


class ChatSendMessageRequest(BaseModel):
    messages: List[MessageItem]
    model: Optional[str] = None
    temperature: Optional[float] = 0.7
    max_tokens: Optional[int] = 1000
    stream: Optional[bool] = False


class ChatSendMessageResponse(BaseModel):
    conversation_id: str
    message_id: str
    role: str
    content: str
    model: str
    tokens: Optional[int] = 0


class ModelGroupInfo(BaseModel):
    group_id: str
    name: str
    providers: List[dict]
    models: List[dict]


class AvailableModelsResponse(BaseModel):
    groups: List[ModelGroupInfo]


def get_user_api_key(db: Session, user_id: str) -> Optional[ApiKey]:
    """获取用户的第一个有效API Key"""
    return db.query(ApiKey).filter(
        ApiKey.user_id == user_id,
        ApiKey.status == ApiKeyStatus.active
    ).first()


def generate_conversation_title(first_message: str) -> str:
    """从第一条消息生成标题"""
    title = first_message.replace("\n", " ").strip()
    return (title[:20] + "...") if len(title) > 20 else (title or "新对话")


@router.get("/models", response_model=AvailableModelsResponse)
async def get_available_models(current_user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    """获取用户可用模型列表"""
    proxy_service = create_proxy_service(db)
    effective_group_ids = proxy_service.get_effective_model_group_ids(current_user)

    if not effective_group_ids:
        return AvailableModelsResponse(groups=[])

    from app.models.model_group import ModelGroup
    from app.models.model import Model, ModelStatus
    from app.models.channel import Channel, ChannelStatus
    from app.models.model_channel import ModelChannel

    groups = db.query(ModelGroup).filter(
        ModelGroup.group_id.in_(effective_group_ids),
        ModelGroup.status == "active"
    ).all()

    result_groups = []
    for group in groups:
        # 获取该分组下可访问的模型（需绑定 enabled channel）
        from sqlalchemy.orm import selectinload
        mappings = (
            db.query(Model)
            .filter(Model.status == ModelStatus.active)
            .join(Model.model_groups)
            .join(Model.model_channels)
            .join(Channel)
            .filter(
                ModelGroup.group_id == group.group_id,
                ModelChannel.enabled == True,
                Channel.status == ChannelStatus.active
            )
            .all()
        )

        result_groups.append(ModelGroupInfo(
            group_id=group.group_id,
            name=group.name,
            providers=[],  # 简化：不再返回 providers
            models=[{"model_id": m.model_id, "display_name": m.display_name, "provider_model": m.model_id} for m in mappings]
        ))

    return AvailableModelsResponse(groups=result_groups)


@router.get("", response_model=ChatConversationListResponse)
async def get_conversations(
    current_user: User = Depends(get_current_user), db: Session = Depends(get_db),
    limit: int = 50, offset: int = 0
):
    """获取对话列表"""
    query = db.query(ChatConversation).filter(ChatConversation.user_id == current_user.user_id)
    total = query.count()
    conversations = query.order_by(ChatConversation.updated_at.desc()).offset(offset).limit(limit).all()

    items = []
    for conv in conversations:
        message_count = db.query(ChatMessage).filter(ChatMessage.conversation_id == conv.conversation_id).count()
        items.append(ChatConversationResponse(
            conversation_id=conv.conversation_id, user_id=conv.user_id, title=conv.title,
            channel_id=conv.channel_id, model_id=conv.model_id, system_prompt=conv.system_prompt,
            created_at=conv.created_at, updated_at=conv.updated_at, message_count=message_count
        ))

    return ChatConversationListResponse(total=total, items=items)


@router.post("", response_model=ChatConversationResponse)
async def create_conversation(
    data: ChatConversationCreate, current_user: User = Depends(get_current_user), db: Session = Depends(get_db)
):
    """创建新对话"""
    conv = ChatConversation(conversation_id=secrets.token_hex(16), user_id=current_user.user_id, title=data.title or "新对话",
                            model_id=data.model, channel_id=data.channel_id, system_prompt=data.system_prompt)
    db.add(conv)
    db.commit()
    db.refresh(conv)
    return ChatConversationResponse(conversation_id=conv.conversation_id, user_id=conv.user_id, title=conv.title,
                                    channel_id=conv.channel_id, model_id=conv.model_id, system_prompt=conv.system_prompt,
                                    created_at=conv.created_at, updated_at=conv.updated_at, message_count=0)


@router.get("/{conversation_id}", response_model=ChatConversationResponse)
async def get_conversation(conversation_id: str, current_user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    """获取对话详情"""
    conv = db.query(ChatConversation).filter(
        ChatConversation.conversation_id == conversation_id,
        ChatConversation.user_id == current_user.user_id
    ).first()
    if not conv:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="对话不存在")
    message_count = db.query(ChatMessage).filter(ChatMessage.conversation_id == conversation_id).count()
    return ChatConversationResponse(conversation_id=conv.conversation_id, user_id=conv.user_id, title=conv.title,
                                    channel_id=conv.channel_id, model_id=conv.model_id, system_prompt=conv.system_prompt,
                                    created_at=conv.created_at, updated_at=conv.updated_at, message_count=message_count)


@router.put("/{conversation_id}", response_model=ChatConversationResponse)
async def update_conversation(
    conversation_id: str, data: ChatConversationUpdate, current_user: User = Depends(get_current_user), db: Session = Depends(get_db)
):
    """更新对话"""
    conv = db.query(ChatConversation).filter(
        ChatConversation.conversation_id == conversation_id,
        ChatConversation.user_id == current_user.user_id
    ).first()
    if not conv:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="对话不存在")
    
    for field in ["title", "model", "channel_id", "system_prompt"]:
        val = getattr(data, field, None)
        if val is not None:
            setattr(conv, field, val)
    
    db.commit()
    db.refresh(conv)
    message_count = db.query(ChatMessage).filter(ChatMessage.conversation_id == conversation_id).count()
    return ChatConversationResponse(conversation_id=conv.conversation_id, user_id=conv.user_id, title=conv.title,
                                    channel_id=conv.channel_id, model_id=conv.model_id, system_prompt=conv.system_prompt,
                                    created_at=conv.created_at, updated_at=conv.updated_at, message_count=message_count)


@router.delete("/{conversation_id}")
async def delete_conversation(conversation_id: str, current_user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    """删除对话"""
    conv = db.query(ChatConversation).filter(
        ChatConversation.conversation_id == conversation_id,
        ChatConversation.user_id == current_user.user_id
    ).first()
    if not conv:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="对话不存在")
    db.delete(conv)
    db.commit()
    return {"message": "对话已删除"}


@router.get("/{conversation_id}/messages", response_model=ChatMessageListResponse)
async def get_messages(conversation_id: str, current_user: User = Depends(get_current_user), db: Session = Depends(get_db), limit: int = 100, offset: int = 0):
    """获取消息列表"""
    conv = db.query(ChatConversation).filter(
        ChatConversation.conversation_id == conversation_id,
        ChatConversation.user_id == current_user.user_id
    ).first()
    if not conv:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="对话不存在")
    
    query = db.query(ChatMessage).filter(ChatMessage.conversation_id == conversation_id)
    total = query.count()
    messages = query.order_by(ChatMessage.created_at.asc()).offset(offset).limit(limit).all()
    
    return ChatMessageListResponse(total=total, items=[
        ChatMessageResponse(message_id=m.message_id, conversation_id=m.conversation_id, role=m.role.value if hasattr(m.role, 'value') else str(m.role),
                           content=m.content, model=m.model, tokens=m.tokens, created_at=m.created_at) for m in messages
    ])


@router.post("/{conversation_id}/messages")
async def send_message(
    conversation_id: str, data: ChatSendMessageRequest, current_user: User = Depends(get_current_user), db: Session = Depends(get_db)
):
    """发送消息"""
    conv = db.query(ChatConversation).filter(
        ChatConversation.conversation_id == conversation_id,
        ChatConversation.user_id == current_user.user_id
    ).first()
    if not conv:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="对话不存在")
    
    api_key = get_user_api_key(db, current_user.user_id)
    if not api_key:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="请先创建API Key")
    
    proxy_service = create_proxy_service(db)
    model = data.model or conv.model_id
    if not model:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="没有可用的模型")
    
    # 前置检查
    group_check = proxy_service.check_model_group_access(api_key, current_user, model)
    if not group_check["allowed"]:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail=group_check["message"])
    
    quota_check = proxy_service.check_quota(current_user, api_key, 1000)
    if not quota_check["allowed"]:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail=quota_check["message"])
    
    # 第一条消息生成标题
    message_count = db.query(ChatMessage).filter(ChatMessage.conversation_id == conversation_id).count()
    if message_count == 0 and data.messages:
        first_user = next((m.content for m in data.messages if m.role == "user"), None)
        if first_user:
            conv.title = generate_conversation_title(first_user)
            db.commit()
    
    # 保存用户消息
    user_msg = ChatMessage(message_id=secrets.token_hex(16), conversation_id=conversation_id, role=MessageRole.user.value,
                          content=data.messages[-1].content if data.messages else "", model=model)
    db.add(user_msg)
    db.commit()
    db.refresh(user_msg)
    
    # 构建请求：清理历史 messages（兼容旧数据 + 上游 alternation 约束）
    messages_for_api = []
    if conv.system_prompt:
        messages_for_api.append({"role": "system", "content": conv.system_prompt})

    def _normalize_role(r):
        s = r.value if hasattr(r, "value") else str(r)
        # 旧数据残留 "MessageRole.user" 这种字符串 → 取最后一段
        if "." in s:
            s = s.rsplit(".", 1)[-1]
        return s

    history = db.query(ChatMessage).filter(ChatMessage.conversation_id == conversation_id).order_by(ChatMessage.created_at.asc()).all()
    cleaned = [
        {"role": _normalize_role(m.role), "content": m.content or ""}
        for m in history
        if m.content is not None  # 跳过空内容
    ]
    # 合并连续同 role 的消息（上游要求 user/assistant 严格交替）
    for item in cleaned:
        role = item["role"]
        if role not in ("user", "assistant", "system"):
            continue
        if messages_for_api and messages_for_api[-1]["role"] == role:
            messages_for_api[-1]["content"] += "\n" + item["content"]
        else:
            messages_for_api.append(dict(item))

    # 收尾：首条必须是 user 或 system；末尾必须是 user（让模型回复）
    while messages_for_api and messages_for_api[0]["role"] == "assistant":
        messages_for_api.pop(0)
    if messages_for_api and messages_for_api[-1]["role"] != "user":
        messages_for_api.pop()
    
    request_data = {"model": model, "messages": messages_for_api, "temperature": data.temperature, "max_tokens": data.max_tokens, "stream": data.stream}
    request_data = {k: v for k, v in request_data.items() if v is not None}
    
    conv.model_id = model
    db.commit()
    
    if data.stream:
        return StreamingResponse(_stream_generator(proxy_service, request_data, conversation_id, user_msg.message_id, current_user, api_key, db),
                                media_type="text/event-stream")
    else:
        result = proxy_service.forward_with_failover(model, current_user, api_key, request_data)
        
        if not result.get("success"):
            raise HTTPException(status_code=result.get("status_code", 500), detail=result.get("error"))
        
        content = ""
        if result.get("data") and "choices" in result["data"]:
            choices = result["data"]["choices"]
            if choices and "message" in choices[0]:
                content = choices[0]["message"].get("content", "")
        
        tokens = proxy_service.calculate_tokens(request_data, result.get("data"))
        
        assistant_msg = ChatMessage(message_id=secrets.token_hex(16), conversation_id=conversation_id, role=MessageRole.assistant.value, content=content, model=model, tokens=tokens.get("total_tokens", 0))
        db.add(assistant_msg)
        
        proxy_service.record_usage(user_id=current_user.user_id, key_id=api_key.key_id, channel_id=result.get("channel_id"),
                                   model=model, tokens=tokens, latency_ms=result.get("latency_ms", 0), status_code=result.get("status_code", 200),
                                   error_message=result.get("error"))
        
        await proxy_service.deduct_quota(current_user, api_key, tokens)
        db.commit()
        
        return ChatSendMessageResponse(conversation_id=conversation_id, message_id=assistant_msg.message_id, role="assistant", content=content, model=model, tokens=tokens.get("total_tokens", 0))


async def _stream_generator(proxy_service, request_data, conversation_id, user_msg_id, current_user, api_key, db):
    """流式响应生成器"""
    content = ""
    try:
        stream_gen = proxy_service.forward_stream(request_data["model"], current_user, api_key, request_data)
        for chunk in stream_gen:
            if chunk.startswith("data: "):
                data_str = chunk[6:]
                if data_str.strip() == "[DONE]":
                    break
                try:
                    data = json.loads(data_str)
                    if "choices" in data and len(data["choices"]) > 0:
                        delta = data["choices"][0].get("delta", {})
                        if "content" in delta:
                            content += delta["content"]
                except Exception:
                    pass
            yield chunk + "\n\n"
        
        assistant_msg = ChatMessage(message_id=secrets.token_hex(16), conversation_id=conversation_id, role=MessageRole.assistant.value, content=content, model=request_data["model"], tokens=len(content) // 4)
        db.add(assistant_msg)
        tokens = {"total_tokens": len(content) // 4, "prompt_tokens": 0, "completion_tokens": len(content) // 4}
        proxy_service.record_usage(user_id=current_user.user_id, key_id=api_key.key_id, channel_id=None, model=request_data["model"],
                                   tokens=tokens, latency_ms=0, status_code=200, error_message=None)
        await proxy_service.deduct_quota(current_user, api_key, tokens)
        db.commit()
    except Exception as e:
        yield f'data: {{"error": "{str(e)}"}}\n\n'
        yield "data: [DONE]\n\n"
