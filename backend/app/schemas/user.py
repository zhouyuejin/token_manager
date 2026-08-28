"""
用户相关Schema
"""
from pydantic import BaseModel, Field
from typing import Optional
from datetime import datetime


class UserBase(BaseModel):
    """用户基础字段"""
    username: str
    email: str


class UserCreate(UserBase):
    """创建用户请求"""
    password: str = Field(..., min_length=8, max_length=32)


class UserUpdate(BaseModel):
    """更新用户请求"""
    email: Optional[str] = None


class UserResponse(UserBase):
    """用户响应"""
    user_id: str
    role: str
    status: str
    quota: int
    quota_used: int
    quota_remain: int
    created_at: datetime
    last_login_at: Optional[datetime] = None

    class Config:
        from_attributes = True


class UserInfo(BaseModel):
    """当前用户信息"""
    user_id: str
    username: str
    email: str
    role: str
    status: str
    quota: int
    quota_used: int
    quota_remain: int
    created_at: str


class PasswordChange(BaseModel):
    """修改密码请求"""
    old_password: str
    new_password: str = Field(..., min_length=8, max_length=32)
