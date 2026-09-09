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

    id = Column(BigInteger, primary_key=True, autoincrement=True)
    conversation_id = Column(String(50), unique=True, nullable=False, index=True)
    user_id = Column(String(32), nullable=False, index=True)
    channel_id = Column(String(32), nullable=True, index=True, comment="渠道ID")
    model = Column(String(50), nullable=False)
    created_at = Column(DateTime, server_default=func.now())
    updated_at = Column(DateTime, server_default=func.now(), onupdate=func.now())


class ChatMessage(Base):
    """聊天消息表"""
    __tablename__ = "chat_messages"

    id = Column(BigInteger, primary_key=True, autoincrement=True)
    conversation_id = Column(String(50), nullable=False, index=True)
    message_id = Column(String(50), unique=True, nullable=False, index=True)
    role = Column(Enum(MessageRole), nullable=False)
    content = Column(Text, nullable=False)
    tokens = Column(Integer, default=0)
    created_at = Column(DateTime, server_default=func.now())
