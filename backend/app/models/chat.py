"""
Chat models - 对话相关数据模型
"""
import uuid
from sqlalchemy import Column, String, Text, DateTime, Integer, ForeignKey, Index
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func

from app.core.database import Base


def generate_uuid() -> str:
    """生成32位UUID字符串"""
    return uuid.uuid4().hex


class ChatConversation(Base):
    """对话会话表"""
    __tablename__ = "chat_conversations"

    conversation_id = Column(String(32), primary_key=True, default=generate_uuid)
    user_id = Column(String(32), nullable=False, index=True, comment="关联用户ID")
    title = Column(String(255), nullable=True, comment="对话标题")
    provider_id = Column(String(32), nullable=True, comment="当前使用的供应商ID")
    model_id = Column(String(32), nullable=True, comment="当前使用的模型ID")
    system_prompt = Column(Text, nullable=True, comment="系统提示词")
    created_at = Column(DateTime, server_default=func.now())
    updated_at = Column(DateTime, server_default=func.now(), onupdate=func.now())

    # 关联消息
    messages = relationship(
        "ChatMessage",
        back_populates="conversation",
        cascade="all, delete-orphan",
        order_by="ChatMessage.created_at"
    )

    # 索引
    __table_args__ = (
        Index("idx_conversation_user_created", "user_id", "created_at"),
    )


class ChatMessage(Base):
    """消息表"""
    __tablename__ = "chat_messages"

    message_id = Column(String(32), primary_key=True, default=generate_uuid)
    conversation_id = Column(
        String(32),
        ForeignKey("chat_conversations.conversation_id", ondelete="CASCADE"),
        nullable=False,
        index=True
    )
    role = Column(String(20), nullable=False, comment="角色: user/assistant/system")
    content = Column(Text, nullable=False, comment="消息内容")
    model = Column(String(50), nullable=True, comment="使用的模型")
    tokens = Column(Integer, nullable=True, comment="token数量")
    created_at = Column(DateTime, server_default=func.now())

    # 关联会话
    conversation = relationship("ChatConversation", back_populates="messages")

    # 索引
    __table_args__ = (
        Index("idx_message_conversation_created", "conversation_id", "created_at"),
    )
