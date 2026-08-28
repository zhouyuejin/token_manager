"""
API Key相关Schema
"""
from pydantic import BaseModel, Field
from typing import Optional, List
from datetime import datetime


class ApiKeyBase(BaseModel):
    """API Key基础字段"""
    key_name: str
    daily_limit: int = 0
    monthly_limit: int = 0
    qps_limit: int = 10


class ApiKeyCreate(ApiKeyBase):
    """创建API Key请求"""
    pass


class ApiKeyUpdate(BaseModel):
    """更新API Key请求"""
    key_name: Optional[str] = None
    daily_limit: Optional[int] = None
    monthly_limit: Optional[int] = None
    qps_limit: Optional[int] = None
    ip_whitelist: Optional[List[str]] = None


class ApiKeyResponse(ApiKeyBase):
    """API Key响应"""
    key_id: str
    user_id: str
    api_key: str
    daily_used: int
    monthly_used: int
    status: str
    created_at: datetime
    last_used_at: Optional[datetime] = None

    class Config:
        from_attributes = True


class ApiKeyListResponse(BaseModel):
    """API Key列表响应"""
    total: int
    items: List[ApiKeyResponse]


class ApiKeyStatusUpdate(BaseModel):
    """更新API Key状态请求"""
    status: str


class ApiKeyCreatedResponse(BaseModel):
    """创建API Key成功响应"""
    key_id: str
    api_key: str
    key_name: str
