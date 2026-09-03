"""
用户接口
"""
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.core.security import verify_password
from app.models.user import User
from app.dependencies import get_current_user
from app.schemas.user import UserInfo, PasswordChange, NotificationSettings

router = APIRouter()


@router.get("/me", response_model=UserInfo)
async def get_current_user_info(current_user: User = Depends(get_current_user)):
    """
    获取当前用户信息
    """
    return UserInfo(
        user_id=current_user.user_id,
        username=current_user.username,
        email=current_user.email,
        role=current_user.role.value,
        status=current_user.status.value,
        quota=current_user.quota,
        quota_used=current_user.quota_used,
        quota_remain=current_user.quota - current_user.quota_used,
        created_at=current_user.created_at.strftime("%Y-%m-%d %H:%M:%S")
    )


@router.put("/me/password")
async def change_password(
    password_data: PasswordChange,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    修改密码 - 密码已在前端进行 SHA256 哈希
    """
    # 验证旧密码（前端传递的已经是哈希后的值）
    if not verify_password(password_data.old_password, current_user.password):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="原密码错误"
        )
    
    # 更新密码（直接存储前端传递的哈希值）
    current_user.password = password_data.new_password
    db.commit()
    
    return {"message": "密码修改成功"}


@router.get("/me/notification-settings", response_model=NotificationSettings)
async def get_notification_settings(
    current_user: User = Depends(get_current_user)
):
    """
    获取当前用户通知设置
    """
    return NotificationSettings(
        quota_low_alert=current_user.quota_low_alert if current_user.quota_low_alert is not None else True,
        quota_change_alert=current_user.quota_change_alert if current_user.quota_change_alert is not None else True,
        daily_report=current_user.daily_report if current_user.daily_report is not None else False
    )


@router.put("/me/notification-settings", response_model=NotificationSettings)
async def update_notification_settings(
    settings: NotificationSettings,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    更新当前用户通知设置
    """
    current_user.quota_low_alert = settings.quota_low_alert
    current_user.quota_change_alert = settings.quota_change_alert
    current_user.daily_report = settings.daily_report
    db.commit()
    
    return NotificationSettings(
        quota_low_alert=current_user.quota_low_alert,
        quota_change_alert=current_user.quota_change_alert,
        daily_report=current_user.daily_report
    )


@router.get("/{user_id}", response_model=UserInfo)
async def get_user_by_id(
    user_id: str,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    根据ID获取用户信息（仅管理员）
    """
    # 检查是否是管理员
    if current_user.role.value != "admin":
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="权限不足"
        )
    
    user = db.query(User).filter(User.user_id == user_id).first()
    if not user:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="用户不存在"
        )
    
    return UserInfo(
        user_id=user.user_id,
        username=user.username,
        email=user.email,
        role=user.role.value,
        status=user.status.value,
        quota=user.quota,
        quota_used=user.quota_used,
        quota_remain=user.quota - user.quota_used,
        created_at=user.created_at.strftime("%Y-%m-%d %H:%M:%S")
    )
