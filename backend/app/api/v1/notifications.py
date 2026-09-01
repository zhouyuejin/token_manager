"""
通知接口
"""
import json
import secrets
from datetime import datetime
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, status, Query
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.models.user import User
from app.models.notification import Notification, NotificationType
from app.dependencies import get_current_user
from app.schemas.notification import (
    NotificationCreate, NotificationResponse,
    NotificationListResponse, UnreadCountResponse
)

router = APIRouter()


def generate_notif_id() -> str:
    """生成通知ID"""
    return f"notif_{secrets.token_hex(8)}"


def notification_to_response(notification: Notification) -> NotificationResponse:
    """将Notification模型转换为响应Schema"""
    return NotificationResponse(
        notif_id=notification.notif_id,
        type=notification.type.value,
        title=notification.title,
        content=notification.content,
        is_read=bool(notification.is_read),
        metadata=json.loads(notification.metadata) if notification.metadata else None,
        created_at=notification.created_at.isoformat() if notification.created_at else None,
        read_at=notification.read_at.isoformat() if notification.read_at else None,
    )


@router.get("", response_model=NotificationListResponse)
async def list_notifications(
    page: int = Query(1, ge=1, description="页码"),
    page_size: int = Query(20, ge=1, le=100, description="每页数量"),
    notif_type: Optional[str] = Query(None, alias="type", description="通知类型筛选"),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    分页获取通知列表
    """
    query = db.query(Notification).filter(
        Notification.user_id == current_user.user_id
    )
    
    # 按类型筛选
    if notif_type:
        try:
            notification_type = NotificationType(notif_type)
            query = query.filter(Notification.type == notification_type)
        except ValueError:
            pass  # 忽略无效的类型
    
    # 获取总数
    total = query.count()
    
    # 获取未读数
    unread_count = query.filter(Notification.is_read == 0).count()
    
    # 分页查询
    offset = (page - 1) * page_size
    notifications = query.order_by(
        Notification.created_at.desc()
    ).offset(offset).limit(page_size).all()
    
    items = [notification_to_response(n) for n in notifications]
    
    return NotificationListResponse(
        total=total,
        unread_count=unread_count,
        items=items
    )


@router.get("/unread-count", response_model=UnreadCountResponse)
async def get_unread_count(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    获取未读通知数量
    """
    unread_count = db.query(Notification).filter(
        Notification.user_id == current_user.user_id,
        Notification.is_read == 0
    ).count()
    
    return UnreadCountResponse(unread_count=unread_count)


@router.put("/{notif_id}/read", response_model=NotificationResponse)
async def mark_notification_read(
    notif_id: str,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    标记单条通知为已读
    """
    notification = db.query(Notification).filter(
        Notification.notif_id == notif_id,
        Notification.user_id == current_user.user_id
    ).first()
    
    if not notification:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="通知不存在"
        )
    
    # 更新为已读
    if notification.is_read == 0:
        notification.is_read = 1
        notification.read_at = datetime.now()
        db.commit()
        db.refresh(notification)
    
    return notification_to_response(notification)


@router.put("/read-all")
async def mark_all_notifications_read(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    全部已读
    """
    # 更新所有未读通知为已读
    result = db.query(Notification).filter(
        Notification.user_id == current_user.user_id,
        Notification.is_read == 0
    ).update({
        Notification.is_read: 1,
        Notification.read_at: datetime.now()
    })
    db.commit()
    
    return {"message": "ok"}


@router.delete("/{notif_id}")
async def delete_notification(
    notif_id: str,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    删除单条通知
    """
    notification = db.query(Notification).filter(
        Notification.notif_id == notif_id,
        Notification.user_id == current_user.user_id
    ).first()
    
    if not notification:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="通知不存在"
        )
    
    db.delete(notification)
    db.commit()
    
    return {"message": "ok"}


@router.delete("")
async def delete_read_notifications(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    清空已读通知
    """
    # 删除当前用户所有已读通知
    result = db.query(Notification).filter(
        Notification.user_id == current_user.user_id,
        Notification.is_read == 1
    ).delete()
    db.commit()
    
    return {"message": "ok", "deleted": result}
