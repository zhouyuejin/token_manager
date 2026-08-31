"""
Chat API - 对话管理接口
"""
import json
from typing import Optional
from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.responses import StreamingResponse
from sqlalchemy.orm import Session
from sqlalchemy import func

from app.core.database import get_db
from app.models.user import User
from app.models.api_key import ApiKey, ApiKeyStatus
from app.models.chat import ChatConversation, ChatMessage
from app.models.model_group import ModelGroup
from app.models.model_mapping import ModelMapping
from app.dependencies import get_current_user
from app.schemas.chat import (
    ChatConversationCreate,
    ChatConversationUpdate,
    ChatConversationResponse,
    ChatConversationListResponse,
    ChatMessageResponse,
    ChatMessageListResponse,
    ChatSendMessageRequest,
    ChatSendMessageResponse,
    ModelGroupInfo,
    AvailableModelsResponse
)
from app.services.proxy_service import ProxyService, create_proxy_service

router = APIRouter()


# ========== 辅助函数 ==========

def get_user_api_key(db: Session, user_id: str) -> Optional[ApiKey]:
    """获取用户的第一个有效API Key"""
    return db.query(ApiKey).filter(
        ApiKey.user_id == user_id,
        ApiKey.status == ApiKeyStatus.active
    ).first()


def generate_conversation_title(first_message: str) -> str:
    """从第一条消息生成标题"""
    # 移除换行符，取前20个字符
    title = first_message.replace("\n", " ").strip()
    if len(title) > 20:
        title = title[:20] + "..."
    return title if title else "新对话"


# ========== API Endpoints ==========

@router.get("/models", response_model=AvailableModelsResponse)
async def get_available_models(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    获取用户可用模型列表
    根据API Key关联的模型分组过滤模型
    """
    # 获取用户的API Key
    api_key = get_user_api_key(db, current_user.user_id)
    
    # 如果没有API Key，返回空列表（让用户可以进入对话页面）
    if not api_key:
        return AvailableModelsResponse(groups=[])
    
    # 获取API Key关联的模型分组
    key_groups = api_key.model_groups
    
    if not key_groups:
        # 没有关联分组，返回所有启用的模型（兼容旧Key）
        mappings = db.query(ModelMapping).filter(
            ModelMapping.status == "active"
        ).all()
        
        if not mappings:
            return AvailableModelsResponse(groups=[])
        
        # 只有一个默认分组
        models = [
            {
                "model_id": mapping.model_id,
                "display_name": mapping.display_name,
                "provider_model": mapping.provider_model
            }
            for mapping in mappings
        ]
        
        return AvailableModelsResponse(groups=[
            ModelGroupInfo(
                group_id="default",
                name="默认模型",
                providers=[],
                models=models
            )
        ])
    
    # 获取分组关联的供应商和模型
    group_ids = [g.group_id for g in key_groups]
    groups = db.query(ModelGroup).filter(
        ModelGroup.group_id.in_(group_ids)
    ).all()
    
    result_groups = []
    for group in groups:
        # 获取分组关联的供应商ID
        provider_ids = [p.provider_id for p in group.providers]
        
        # 获取这些供应商的模型映射
        mappings = db.query(ModelMapping).filter(
            ModelMapping.status == "active",
            ModelMapping.provider_id.in_(provider_ids)
        ).all() if provider_ids else []
        
        models = [
            {
                "model_id": mapping.model_id,
                "display_name": mapping.display_name,
                "provider_model": mapping.provider_model
            }
            for mapping in mappings
        ]
        
        # 获取供应商信息
        providers = [
            {
                "provider_id": p.provider_id,
                "name": p.name,
                "type": p.type.value if hasattr(p.type, 'value') else str(p.type)
            }
            for p in group.providers
        ]
        
        result_groups.append(ModelGroupInfo(
            group_id=group.group_id,
            name=group.name,
            providers=providers,
            models=models
        ))
    
    return AvailableModelsResponse(groups=result_groups)


@router.get("", response_model=ChatConversationListResponse)
async def get_conversations(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
    limit: int = 50,
    offset: int = 0
):
    """
    获取对话列表
    """
    # 查询用户的对话
    query = db.query(ChatConversation).filter(
        ChatConversation.user_id == current_user.user_id
    )
    
    # 获取总数
    total = query.count()
    
    # 获取分页列表
    conversations = query.order_by(
        ChatConversation.updated_at.desc()
    ).offset(offset).limit(limit).all()
    
    # 获取每个对话的消息数量
    items = []
    for conv in conversations:
        message_count = db.query(ChatMessage).filter(
            ChatMessage.conversation_id == conv.conversation_id
        ).count()
        
        items.append(ChatConversationResponse(
            conversation_id=conv.conversation_id,
            user_id=conv.user_id,
            title=conv.title,
            provider_id=conv.provider_id,
            model_id=conv.model_id,
            system_prompt=conv.system_prompt,
            created_at=conv.created_at,
            updated_at=conv.updated_at,
            message_count=message_count
        ))
    
    return ChatConversationListResponse(total=total, items=items)


@router.post("", response_model=ChatConversationResponse)
async def create_conversation(
    conversation_data: ChatConversationCreate,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    创建新对话
    """
    conversation = ChatConversation(
        user_id=current_user.user_id,
        title=conversation_data.title,
        model_id=conversation_data.model,
        provider_id=conversation_data.provider_id,
        system_prompt=conversation_data.system_prompt
    )
    
    db.add(conversation)
    db.commit()
    db.refresh(conversation)
    
    return ChatConversationResponse(
        conversation_id=conversation.conversation_id,
        user_id=conversation.user_id,
        title=conversation.title,
        provider_id=conversation.provider_id,
        model_id=conversation.model_id,
        system_prompt=conversation.system_prompt,
        created_at=conversation.created_at,
        updated_at=conversation.updated_at,
        message_count=0
    )


@router.get("/{conversation_id}", response_model=ChatConversationResponse)
async def get_conversation(
    conversation_id: str,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    获取对话详情
    """
    conversation = db.query(ChatConversation).filter(
        ChatConversation.conversation_id == conversation_id,
        ChatConversation.user_id == current_user.user_id
    ).first()
    
    if not conversation:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="对话不存在"
        )
    
    # 获取消息数量
    message_count = db.query(ChatMessage).filter(
        ChatMessage.conversation_id == conversation_id
    ).count()
    
    return ChatConversationResponse(
        conversation_id=conversation.conversation_id,
        user_id=conversation.user_id,
        title=conversation.title,
        provider_id=conversation.provider_id,
        model_id=conversation.model_id,
        system_prompt=conversation.system_prompt,
        created_at=conversation.created_at,
        updated_at=conversation.updated_at,
        message_count=message_count
    )


@router.put("/{conversation_id}", response_model=ChatConversationResponse)
async def update_conversation(
    conversation_id: str,
    conversation_data: ChatConversationUpdate,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    更新对话
    """
    conversation = db.query(ChatConversation).filter(
        ChatConversation.conversation_id == conversation_id,
        ChatConversation.user_id == current_user.user_id
    ).first()
    
    if not conversation:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="对话不存在"
        )
    
    # 更新字段
    if conversation_data.title is not None:
        conversation.title = conversation_data.title
    if conversation_data.model is not None:
        conversation.model_id = conversation_data.model
    if conversation_data.provider_id is not None:
        conversation.provider_id = conversation_data.provider_id
    if conversation_data.system_prompt is not None:
        conversation.system_prompt = conversation_data.system_prompt
    
    db.commit()
    db.refresh(conversation)
    
    # 获取消息数量
    message_count = db.query(ChatMessage).filter(
        ChatMessage.conversation_id == conversation_id
    ).count()
    
    return ChatConversationResponse(
        conversation_id=conversation.conversation_id,
        user_id=conversation.user_id,
        title=conversation.title,
        provider_id=conversation.provider_id,
        model_id=conversation.model_id,
        system_prompt=conversation.system_prompt,
        created_at=conversation.created_at,
        updated_at=conversation.updated_at,
        message_count=message_count
    )


@router.delete("/{conversation_id}")
async def delete_conversation(
    conversation_id: str,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    删除对话
    """
    conversation = db.query(ChatConversation).filter(
        ChatConversation.conversation_id == conversation_id,
        ChatConversation.user_id == current_user.user_id
    ).first()
    
    if not conversation:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="对话不存在"
        )
    
    # 删除对话（级联删除消息）
    db.delete(conversation)
    db.commit()
    
    return {"message": "对话已删除"}


@router.get("/{conversation_id}/messages", response_model=ChatMessageListResponse)
async def get_messages(
    conversation_id: str,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
    limit: int = 100,
    offset: int = 0
):
    """
    获取消息列表
    """
    # 验证对话属于当前用户
    conversation = db.query(ChatConversation).filter(
        ChatConversation.conversation_id == conversation_id,
        ChatConversation.user_id == current_user.user_id
    ).first()
    
    if not conversation:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="对话不存在"
        )
    
    # 查询消息
    query = db.query(ChatMessage).filter(
        ChatMessage.conversation_id == conversation_id
    )
    
    # 获取总数
    total = query.count()
    
    # 获取消息列表
    messages = query.order_by(
        ChatMessage.created_at.asc()
    ).offset(offset).limit(limit).all()
    
    items = [
        ChatMessageResponse(
            message_id=msg.message_id,
            conversation_id=msg.conversation_id,
            role=msg.role,
            content=msg.content,
            model=msg.model,
            tokens=msg.tokens,
            created_at=msg.created_at
        )
        for msg in messages
    ]
    
    return ChatMessageListResponse(total=total, items=items)


@router.post("/{conversation_id}/messages")
async def send_message(
    conversation_id: str,
    message_request: ChatSendMessageRequest,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    发送消息
    支持流式和非流式响应
    """
    # 验证对话属于当前用户
    conversation = db.query(ChatConversation).filter(
        ChatConversation.conversation_id == conversation_id,
        ChatConversation.user_id == current_user.user_id
    ).first()
    
    if not conversation:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="对话不存在"
        )
    
    # 获取用户的API Key
    api_key = get_user_api_key(db, current_user.user_id)
    if not api_key:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="请先创建API Key"
        )
    
    # 如果是第一条消息，自动生成标题
    message_count = db.query(ChatMessage).filter(
        ChatMessage.conversation_id == conversation_id
    ).count()
    
    if message_count == 0 and message_request.messages:
        first_user_message = next(
            (m.content for m in message_request.messages if m.role == "user"),
            None
        )
        if first_user_message:
            conversation.title = generate_conversation_title(first_user_message)
            db.commit()
    
    # 确定使用的模型
    model = message_request.model or conversation.model_id
    if not model:
        # 获取第一个可用的模型
        mapping = db.query(ModelMapping).filter(
            ModelMapping.status == "active"
        ).first()
        if mapping:
            model = mapping.model_id
        else:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="没有可用的模型"
            )
    
    # 保存用户消息
    user_message = ChatMessage(
        conversation_id=conversation_id,
        role="user",
        content=message_request.messages[-1].content if message_request.messages else "",
        model=model
    )
    db.add(user_message)
    db.commit()
    db.refresh(user_message)
    
    # 获取代理服务
    proxy_service = create_proxy_service(db)
    
    # 获取模型映射
    model_mapping = proxy_service.get_model_mapping(model)
    if not model_mapping:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"不支持的模型: {model}"
        )
    
    # 获取供应商
    provider = proxy_service.get_provider(model_mapping.provider_id)
    if not provider:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="供应商不可用"
        )
    
    # 构建请求数据
    messages_for_api = []
    
    # 添加系统提示词
    if conversation.system_prompt:
        messages_for_api.append({
            "role": "system",
            "content": conversation.system_prompt
        })
    
    # 添加历史消息
    history_messages = db.query(ChatMessage).filter(
        ChatMessage.conversation_id == conversation_id
    ).order_by(ChatMessage.created_at.asc()).all()
    
    for msg in history_messages:
        messages_for_api.append({
            "role": msg.role,
            "content": msg.content
        })
    
    # 添加当前用户消息
    if message_request.messages:
        messages_for_api.append({
            "role": "user",
            "content": message_request.messages[-1].content
        })
    
    request_data = {
        "model": model_mapping.provider_model,
        "messages": messages_for_api,
        "temperature": message_request.temperature,
        "max_tokens": message_request.max_tokens,
        "stream": message_request.stream
    }
    
    # 移除None值
    request_data = {k: v for k, v in request_data.items() if v is not None}
    
    # 更新对话的模型和供应商
    conversation.model_id = model
    conversation.provider_id = model_mapping.provider_id
    db.commit()
    
    if message_request.stream:
        # 流式响应
        return StreamingResponse(
            _stream_generator(
                proxy_service, provider, model_mapping, request_data,
                conversation_id, user_message.message_id, current_user, api_key, db
            ),
            media_type="text/event-stream"
        )
    else:
        # 非流式响应
        result = proxy_service.forward_request(provider, model_mapping, request_data)
        
        if not result["success"]:
            raise HTTPException(
                status_code=result["status_code"],
                detail=result["error"]
            )
        
        # 提取回复内容
        content = ""
        if result["data"] and "choices" in result["data"]:
            choices = result["data"]["choices"]
            if choices and "message" in choices[0]:
                content = choices[0]["message"].get("content", "")
        
        # 计算token数量
        tokens = proxy_service.calculate_tokens(request_data, result["data"])
        
        # 保存助手消息
        assistant_message = ChatMessage(
            conversation_id=conversation_id,
            role="assistant",
            content=content,
            model=model,
            tokens=tokens.get("total_tokens", 0)
        )
        db.add(assistant_message)
        
        # 记录用量
        proxy_service.record_usage(
            user_id=current_user.user_id,
            key_id=api_key.key_id,
            provider_id=provider.provider_id,
            model=model,
            tokens=tokens,
            latency_ms=result["latency_ms"],
            status_code=result["status_code"],
            error_message=result["error"]
        )
        
        # 扣减额度
        if result["success"] and result["status_code"] == 200:
            proxy_service.deduct_quota(current_user, api_key, tokens)
        
        db.commit()
        
        return ChatSendMessageResponse(
            conversation_id=conversation_id,
            message_id=assistant_message.message_id,
            role="assistant",
            content=content,
            model=model,
            tokens=tokens.get("total_tokens", 0)
        )


async def _stream_generator(
    proxy_service: ProxyService,
    provider,
    model_mapping,
    request_data: dict,
    conversation_id: str,
    user_message_id: str,
    current_user: User,
    api_key: ApiKey,
    db: Session
):
    """流式响应生成器"""
    content = ""
    
    try:
        stream_generator, _ = proxy_service.forward_stream_request(provider, model_mapping, request_data)
        for chunk in stream_generator:
            # 解析chunk，提取内容
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
                            yield chunk + "\n\n"
                except:
                    yield chunk + "\n\n"
            else:
                yield chunk + "\n\n"
        
        # 保存助手消息
        assistant_message = ChatMessage(
            conversation_id=conversation_id,
            role="assistant",
            content=content,
            model=model_mapping.model_id,
            tokens=len(content) // 4  # 简单估算
        )
        db.add(assistant_message)
        
        # 记录用量
        tokens = {"total_tokens": len(content) // 4, "prompt_tokens": 0, "completion_tokens": len(content) // 4}
        proxy_service.record_usage(
            user_id=current_user.user_id,
            key_id=api_key.key_id,
            provider_id=provider.provider_id,
            model=model_mapping.model_id,
            tokens=tokens,
            latency_ms=0,
            status_code=200,
            error_message=None
        )
        
        # 扣减额度
        proxy_service.deduct_quota(current_user, api_key, tokens)
        
        db.commit()
        
    except Exception as e:
        yield f'data: {{"error": "{str(e)}"}}\n\n'
        yield "data: [DONE]\n\n"
