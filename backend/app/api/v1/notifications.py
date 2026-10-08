"""
通知接口
"""
import secrets
from datetime import datetime
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, status, Query
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.models.user import User
from app.models.notification import Notification, NotificationType
from app.models.project import Project
from app.dependencies import get_current_user
from app.schemas.notification import (
    NotificationCreate, NotificationResponse,
    NotificationListResponse, UnreadCountResponse
)

router = APIRouter()


def generate_notif_id() -> str:
    """生成通知ID"""
    return f"notif_{secrets.token_hex(8)}"


def notification_to_response(notification: Notification, project_names=None) -> NotificationResponse:
    """将Notification模型转换为响应Schema"""
    metadata = notification.metadata_dict
    content = notification.content
    if metadata and metadata.get("kind") == "project_usage_growth" and project_names:
        project_id = metadata.get("project_id")
        name = project_names.get(project_id)
        if name and content:
            content = content.replace(f"项目 {project_id} ", f"项目 {name} ", 1)
    return NotificationResponse(
        notif_id=notification.notif_id,
        type=notification.type.value,
        title=notification.title,
        content=content,
        is_read=bool(notification.is_read),
        metadata=metadata,
        created_at=notification.created_at,
        read_at=notification.read_at,
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
    
    project_ids = {n.metadata_dict.get("project_id") for n in notifications
                   if n.metadata_dict and n.metadata_dict.get("kind") == "project_usage_growth"}
    project_names = dict(db.query(Project.project_id, Project.name).filter(Project.project_id.in_(project_ids)).all()) if project_ids else {}
    items = [notification_to_response(n, project_names) for n in notifications]
    
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
    
    metadata = notification.metadata_dict
    project = db.query(Project).filter_by(project_id=metadata["project_id"]).first() if metadata and metadata.get("kind") == "project_usage_growth" and metadata.get("project_id") else None
    return notification_to_response(notification, {project.project_id: project.name} if project else {})


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
