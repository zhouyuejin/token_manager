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
