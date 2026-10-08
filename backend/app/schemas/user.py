"""
用户相关Schema
"""
from pydantic import BaseModel, EmailStr, Field, computed_field, BeforeValidator
from typing import Optional, List, Annotated
from datetime import datetime
from app.schemas._datetime import UtcDateTime


Nickname = Annotated[Optional[str], Field(max_length=50), BeforeValidator(
    lambda value: (value.strip() or None) if isinstance(value, str) else value
)]


class UserProfileUpdate(BaseModel):
    """用户仅可维护自己的昵称。"""
    nickname: Nickname


class UserBase(BaseModel):
    """用户基础字段"""
    username: str
    nickname: Nickname = None
    email: EmailStr


class UserCreate(UserBase):
    """创建用户请求"""
    password: str = Field(..., min_length=8, max_length=32)
    role: str = "user"
    model_group_ids: Optional[List[str]] = Field(default_factory=list)


class UserUpdate(BaseModel):
    """更新用户请求"""
    nickname: Nickname = None
    email: Optional[EmailStr] = None
    role: Optional[str] = None
    model_group_ids: Optional[List[str]] = None


class UserResponse(UserBase):
    """用户响应"""
    user_id: str
    role: str
    status: str
    quota: int
    quota_used: int
    quota_remain: int
    created_at: UtcDateTime
    last_login_at: Optional[UtcDateTime] = None
    model_group_ids: List[str] = Field(default_factory=list)

    @computed_field
    @property
    def unlimited(self) -> bool:
        return self.quota < 0

    class Config:
        from_attributes = True


class UserInfo(BaseModel):
    """当前用户信息"""
    user_id: str
    username: str
    nickname: Nickname = None
    email: str
    role: str
    status: str
    quota: int
    quota_used: int
    quota_remain: int
    created_at: str
    permissions: List[str] = Field(default_factory=list)

    @computed_field
    @property
    def unlimited(self) -> bool:
        return self.quota < 0


class PasswordChange(BaseModel):
    """修改密码请求"""
    old_password: str
    # 注：自 feat(auth) 9e5d780 起，密码已是前端 SHA256 hex（固定 64 字符），
    # 长度上限对应放宽。min_length=8 保持原意（不允许过短 hex）。
    new_password: str = Field(..., min_length=8, max_length=64)


class NotificationSettings(BaseModel):
    """通知设置"""
    quota_low_alert: bool = True
    quota_change_alert: bool = True
    daily_report: bool = False

    class Config:
        from_attributes = True
