"""
聊天会话模型
"""
from sqlalchemy import Column, BigInteger, String, Enum, DateTime, Text, Integer
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func

from app.core.database import Base
import enum


class MessageRole(enum.Enum):
    """消息角色"""
    system = "system"
    user = "user"
    assistant = "assistant"


class ChatConversation(Base):
    """聊天会话表"""
    __tablename__ = "chat_conversations"

    conversation_id = Column(String(32), primary_key=True)
    user_id = Column(String(32), nullable=False, index=True)
    channel_id = Column(String(32), nullable=True, index=True, comment="渠道ID")
    model_id = Column(String(50), nullable=False, comment="模型ID")
    title = Column(String(255), nullable=True)
    system_prompt = Column(Text, nullable=True)
    created_at = Column(DateTime, server_default=func.now())
    updated_at = Column(DateTime, server_default=func.now(), onupdate=func.now())


class ChatMessage(Base):
    """聊天消息表"""
    __tablename__ = "chat_messages"

    message_id = Column(String(32), primary_key=True)
    conversation_id = Column(String(32), nullable=False, index=True)
    role = Column(String(20), nullable=False)
    content = Column(Text, nullable=False)
    model = Column(String(50), nullable=True)
    tokens = Column(Integer, default=0)
    created_at = Column(DateTime, server_default=func.now())
