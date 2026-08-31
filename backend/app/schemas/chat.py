"""
Chat相关Schema
"""
from pydantic import BaseModel, Field
from typing import Optional, List
from datetime import datetime


class ChatMessageCreate(BaseModel):
    """创建消息请求"""
    role: str = Field(..., description="角色: user/assistant/system")
    content: str = Field(..., description="消息内容")


class ChatMessageResponse(BaseModel):
    """消息响应"""
    message_id: str
    conversation_id: str
    role: str
    content: str
    model: Optional[str] = None
    tokens: Optional[int] = None
    created_at: datetime

    class Config:
        from_attributes = True


class ChatMessageListResponse(BaseModel):
    """消息列表响应"""
    total: int
    items: List[ChatMessageResponse]


class ChatConversationCreate(BaseModel):
    """创建对话请求"""
    title: Optional[str] = Field(None, description="对话标题(可选)")
    model: Optional[str] = Field(None, description="使用的模型(可选)")
    provider_id: Optional[str] = Field(None, description="供应商ID(可选)")
    system_prompt: Optional[str] = Field(None, description="系统提示词(可选)")


class ChatConversationUpdate(BaseModel):
    """更新对话请求"""
    title: Optional[str] = Field(None, description="对话标题")
    model: Optional[str] = Field(None, description="使用的模型")
    provider_id: Optional[str] = Field(None, description="供应商ID")
    system_prompt: Optional[str] = Field(None, description="系统提示词")


class ChatConversationResponse(BaseModel):
    """对话响应"""
    conversation_id: str
    user_id: str
    title: Optional[str] = None
    provider_id: Optional[str] = None
    model_id: Optional[str] = None
    system_prompt: Optional[str] = None
    created_at: datetime
    updated_at: datetime
    message_count: Optional[int] = 0  # 消息数量

    class Config:
        from_attributes = True


class ChatConversationListResponse(BaseModel):
    """对话列表响应"""
    total: int
    items: List[ChatConversationResponse]


class ChatSendMessageRequest(BaseModel):
    """发送消息请求"""
    messages: List[ChatMessageCreate] = Field(..., description="消息列表")
    model: Optional[str] = Field(None, description="使用的模型")
    temperature: Optional[float] = Field(0.7, description="温度参数")
    max_tokens: Optional[int] = Field(1000, description="最大token数")
    stream: Optional[bool] = Field(False, description="是否流式输出")
    provider_id: Optional[str] = Field(None, description="供应商ID(可选)")


class ChatSendMessageResponse(BaseModel):
    """发送消息响应(非流式)"""
    conversation_id: str
    message_id: str
    role: str
    content: str
    model: str
    tokens: Optional[int] = None


class ModelGroupInfo(BaseModel):
    """模型分组信息"""
    group_id: str
    name: str
    providers: List[dict] = []  # 供应商列表
    models: List[dict] = []    # 模型列表


class AvailableModelsResponse(BaseModel):
    """可用模型响应"""
    groups: List[ModelGroupInfo]
