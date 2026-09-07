"""
通知相关Schema
"""
from pydantic import BaseModel
from typing import Optional, List
from datetime import datetime
from app.schemas._datetime import UtcDateTime


class NotificationCreate(BaseModel):
    """创建通知请求"""
    user_id: str
    type: str
    title: str
    content: Optional[str] = None
    metadata: Optional[dict] = None


class NotificationResponse(BaseModel):
    """通知响应"""
    notif_id: str
    type: str
    title: str
    content: Optional[str]
    is_read: bool
    metadata: Optional[dict]
    created_at: UtcDateTime
    read_at: Optional[UtcDateTime]
    
    class Config:
        from_attributes = True


class NotificationListResponse(BaseModel):
    """通知列表响应"""
    total: int
    unread_count: int
    items: List[NotificationResponse]


class UnreadCountResponse(BaseModel):
    """未读数量响应"""
    unread_count: int
