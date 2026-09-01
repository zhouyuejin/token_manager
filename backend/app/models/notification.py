"""
通知模型
"""
import enum
from sqlalchemy import Column, BigInteger, String, Enum, DateTime, Text, Index
from sqlalchemy.sql import func

from app.core.database import Base


class NotificationType(enum.Enum):
    """通知类型"""
    quota_low = "quota_low"
    quota_increase = "quota_increase"
    quota_decrease = "quota_decrease"
    daily_report = "daily_report"
    system = "system"


class Notification(Base):
    """通知表"""
    __tablename__ = "notifications"
    
    id = Column(BigInteger, primary_key=True, autoincrement=True)
    notif_id = Column(String(32), unique=True, nullable=False, index=True)
    user_id = Column(String(32), nullable=False, index=True)
    type = Column(Enum(NotificationType), nullable=False)
    title = Column(String(100), nullable=False)
    content = Column(Text, nullable=True)
    is_read = Column(BigInteger, default=0)
    extra_data = Column(Text, nullable=True)   # JSON 格式存储附加数据
    created_at = Column(DateTime, server_default=func.now())
    read_at = Column(DateTime, nullable=True)
    
    __table_args__ = (
        Index('idx_user_unread', 'user_id', 'is_read'),
        Index('idx_user_created', 'user_id', 'created_at'),
    )
    
    def to_dict(self):
        import json
        return {
            "notif_id": self.notif_id,
            "user_id": self.user_id,
            "type": self.type.value,
            "title": self.title,
            "content": self.content,
            "is_read": bool(self.is_read),
            "metadata": json.loads(self.extra_data) if self.extra_data else None,
            "created_at": self.created_at.isoformat() if self.created_at else None,
            "read_at": self.read_at.isoformat() if self.read_at else None,
        }
