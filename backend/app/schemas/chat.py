"""
聊天相关Schema
"""
from pydantic import BaseModel, Field
from typing import Optional, List, Dict, Any
from app.schemas._datetime import UtcDateTime


class ChatMessage(BaseModel):
    """聊天消息"""
    role: str  # system, user, assistant
    content: str


class ChatCompletionRequest(BaseModel):
    """Chat Completion 请求"""
    model: str = Field(..., description="模型 ID")
    messages: List[ChatMessage]
    temperature: Optional[float] = 1.0
    top_p: Optional[float] = None
    n: Optional[int] = 1
    stream: Optional[bool] = False
    stop: Optional[List[str]] = None
    max_tokens: Optional[int] = None
    presence_penalty: Optional[float] = None
    frequency_penalty: Optional[float] = None
    user: Optional[str] = None
    # 扩展参数
    response_format: Optional[Dict[str, str]] = None
    tools: Optional[List[Dict[str, Any]]] = None
    tool_choice: Optional[Any] = None
    stream_options: Optional[Dict[str, Any]] = None


class ChatCompletionResponse(BaseModel):
    """Chat Completion 响应"""
    id: str
    object: str = "chat.completion"
    created: int
    model: str
    choices: List[Dict[str, Any]]
    usage: Dict[str, int]
    service_tier: Optional[str] = None


class ChatConversationResponse(BaseModel):
    """会话响应"""
    conversation_id: str
    user_id: str
    channel_id: Optional[str] = None  # 改为 channel_id
    model: str
    created_at: UtcDateTime
    messages: List[ChatMessage] = []


class StreamChunk(BaseModel):
    """流式响应chunk"""
    id: str
    object: str = "chat.completion.chunk"
    created: int
    model: str
    choices: List[Dict[str, Any]]
    delta: Optional[Dict[str, Any]] = None


# === 补充缺失的 Schema（向后兼容）===

class ChatMessageCreate(BaseModel):
    """创建聊天消息"""
    role: str
    content: str


class ChatMessageResponse(BaseModel):
    """聊天消息响应"""
    id: str
    conversation_id: str
    role: str
    content: str
    model: Optional[str] = None
    created_at: Optional[UtcDateTime] = None


class ChatMessageListResponse(BaseModel):
    """聊天消息列表响应"""
    messages: List[ChatMessageResponse]
    total: int


class ChatConversationCreate(BaseModel):
    """创建会话"""
    user_id: str
    title: Optional[str] = None


class ChatConversationUpdate(BaseModel):
    """更新会话"""
    title: Optional[str] = None


class ChatConversationListResponse(BaseModel):
    """会话列表响应"""
    conversations: List[ChatConversationResponse]
    total: int


class ChatSendMessageRequest(BaseModel):
    """发送消息请求"""
    conversation_id: Optional[str] = None
    message: str
    model: str
    stream: Optional[bool] = False
    temperature: Optional[float] = 1.0
    top_p: Optional[float] = None
    max_tokens: Optional[int] = None


class ChatSendMessageResponse(BaseModel):
    """发送消息响应"""
    conversation_id: str
    message_id: str
    content: str
    model: str
    usage: Optional[Dict[str, int]] = None


class ModelGroupInfo(BaseModel):
    """模型组信息"""
    id: str
    name: str
    models: List[str]
    priority: int = 0


class AvailableModelsResponse(BaseModel):
    """可用模型响应"""
    models: List[ModelGroupInfo]
    total: int
