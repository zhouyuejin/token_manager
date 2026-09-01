"""
通知服务
"""
import json
import secrets
from datetime import datetime
from typing import Optional, List

from sqlalchemy.orm import Session
from app.models.notification import Notification, NotificationType

# 全局 manager 实例（从 ws_manager 导入）
from app.services.ws_manager import manager as ws_manager


async def create_notification(
    db: Session,
    user_id: str,
    notif_type: NotificationType,
    title: str,
    content: Optional[str] = None,
    metadata: Optional[dict] = None
) -> Notification:
    """创建通知并存入数据库，同时通过 WebSocket 推送"""
    notif_id = f"notif_{secrets.token_hex(8)}"
    notif = Notification(
        notif_id=notif_id,
        user_id=user_id,
        type=notif_type,
        title=title,
        content=content,
        extra_data=json.dumps(metadata) if metadata else None,
        is_read=0,
    )
    db.add(notif)
    db.commit()
    db.refresh(notif)
    
    # WebSocket 实时推送
    try:
        await ws_manager.send_to_user(user_id, {
            "type": "new_notification",
            "notif": notif.to_dict()
        })
    except Exception:
        pass  # WebSocket 推送失败不影响通知创建
    
    return notif


async def get_unread_count(user_id: str, db: Session) -> int:
    """获取用户未读通知数"""
    return db.query(Notification).filter(
        Notification.user_id == user_id,
        Notification.is_read == 0
    ).count()


def mark_as_read(db: Session, notif_id: str, user_id: str) -> bool:
    """标记单条已读"""
    notif = db.query(Notification).filter(
        Notification.notif_id == notif_id,
        Notification.user_id == user_id
    ).first()
    if not notif:
        return False
    if notif.is_read == 0:
        notif.is_read = 1
        notif.read_at = datetime.now()
        db.commit()
    return True


def mark_all_as_read(db: Session, user_id: str) -> int:
    """全部已读，返回更新条数"""
    count = db.query(Notification).filter(
        Notification.user_id == user_id,
        Notification.is_read == 0
    ).update({"is_read": 1, "read_at": datetime.now()})
    db.commit()
    return count


def delete_notification(db: Session, notif_id: str, user_id: str) -> bool:
    """删除单条通知"""
    notif = db.query(Notification).filter(
        Notification.notif_id == notif_id,
        Notification.user_id == user_id
    ).first()
    if not notif:
        return False
    db.delete(notif)
    db.commit()
    return True


def get_notification_list(
    db: Session, user_id: str, 
    page: int = 1, page_size: int = 20, 
    notif_type: Optional[str] = None
) -> tuple[List[Notification], int, int]:
    """分页查询通知列表，返回 (items, total, unread_count)"""
    query = db.query(Notification).filter(Notification.user_id == user_id)
    if notif_type:
        query = query.filter(Notification.type == notif_type)
    
    total = query.count()
    unread_count = db.query(Notification).filter(
        Notification.user_id == user_id,
        Notification.is_read == 0
    ).count()
    
    items = query.order_by(Notification.created_at.desc()) \
        .offset((page - 1) * page_size) \
        .limit(page_size).all()
    
    return items, total, unread_count
