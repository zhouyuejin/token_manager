"""
通知服务
"""
import json
import secrets
from datetime import datetime
from typing import Optional, List
from loguru import logger

from sqlalchemy.orm import Session
from app.models.notification import Notification, NotificationType
from app.models.user import User, UserRole

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
    
    logger.info(f"[通知] 创建通知 {notif_id} 给用户 {user_id}，类型: {notif_type.value}")
    
    # WebSocket 实时推送
    try:
        ws_result = await ws_manager.send_to_user(user_id, {
            "type": "new_notification",
            "notif": notif.to_dict()
        })
        if ws_result:
            logger.info(f"[通知] WebSocket 推送成功 {notif_id} 给用户 {user_id}")
        else:
            logger.warning(f"[通知] WebSocket 推送失败 {notif_id} 给用户 {user_id}，用户可能未连接")
    except Exception as e:
        logger.error(f"[通知] WebSocket 推送异常 {notif_id} 给用户 {user_id}: {e}")
    
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


async def notify_admins_new_user(db: Session, user: User) -> None:
    """
    向所有管理员发送新用户注册通知。

    每个管理员的通知使用 SAVEPOINT 隔离写入：单个通知失败只回滚自身，
    不污染调用方的 db session，保证 /register 后续逻辑（如读取 user 属性）
    不会被连带 500。
    """
    try:
        admins = db.query(User).filter(User.role == UserRole.admin).all()
    except Exception as e:
        logger.warning(f"[通知] 查询管理员列表失败: {e}")
        return

    saved_count = 0
    for admin in admins:
        savepoint = db.begin_nested()
        try:
            notif_id = f"notif_{secrets.token_hex(8)}"
            notif = Notification(
                notif_id=notif_id,
                user_id=admin.user_id,
                type=NotificationType.user_registered,
                title="新用户注册",
                content=f"用户 {user.username}（{user.email}）已注册，等待分配权限和额度。",
                extra_data=json.dumps({"user_id": user.user_id, "username": user.username}),
                is_read=0,
            )
            db.add(notif)
            db.flush()
            db.refresh(notif)
            savepoint.commit()
            saved_count += 1

            logger.info(f"[通知] 创建通知 {notif_id} 给用户 {admin.user_id}，类型: {NotificationType.user_registered.value}")

            # WebSocket 实时推送
            try:
                ws_result = await ws_manager.send_to_user(admin.user_id, {
                    "type": "new_notification",
                    "notif": notif.to_dict()
                })
                if ws_result:
                    logger.info(f"[通知] WebSocket 推送成功 {notif_id} 给用户 {admin.user_id}")
                else:
                    logger.warning(f"[通知] WebSocket 推送失败 {notif_id} 给用户 {admin.user_id}，用户可能未连接")
            except Exception as e:
                logger.error(f"[通知] WebSocket 推送异常 {notif_id} 给用户 {admin.user_id}: {e}")
        except Exception as e:
            savepoint.rollback()
            logger.warning(f"[通知] 发送给管理员 {admin.user_id} 失败: {e}")
            continue

    # 至少有一条通知成功 flush 时，提交外层事务使其落库
    if saved_count > 0:
        try:
            db.commit()
        except Exception as e:
            logger.warning(f"[通知] 提交新用户注册通知失败: {e}")
