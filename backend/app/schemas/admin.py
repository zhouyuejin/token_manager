"""
管理后台相关Schema
"""
from pydantic import BaseModel, Field
from typing import Optional, List
from datetime import datetime


# ========== 用户管理 ==========

class AdminUserCreate(BaseModel):
    """管理员创建用户请求"""
    username: str
    email: str
    password: str = Field(..., min_length=8)
    role: str = "user"
    quota: int = 0


class AdminUserUpdate(BaseModel):
    """管理员更新用户请求"""
    role: Optional[str] = None
    status: Optional[str] = None
    quota: Optional[int] = None


class AdminUserResponse(BaseModel):
    """用户响应"""
    user_id: str
    username: str
    email: str
    role: str
    status: str
    quota: int
    quota_used: int
    created_at: datetime

    class Config:
        from_attributes = True


class UserListResponse(BaseModel):
    """用户列表响应"""
    total: int
    items: List[AdminUserResponse]


class QuotaAdjustRequest(BaseModel):
    """额度调整请求"""
    amount: int
    reason: str


# ========== 供应商管理 ==========

class ProviderCreate(BaseModel):
    """创建供应商请求"""
    name: str
    type: str
    endpoint: str
    api_key: str
    priority: int = 100
    timeout: int = 60
    quota_hourly: int = 0
    quota_weekly: int = 0
    sync_enabled: bool = False
    sync_interval: int = 300  # 默认5分钟


class ProviderUpdate(BaseModel):
    """更新供应商请求"""
    name: Optional[str] = None
    type: Optional[str] = None
    endpoint: Optional[str] = None
    api_key: Optional[str] = None
    priority: Optional[int] = None
    timeout: Optional[int] = None
    status: Optional[str] = None
    quota_hourly: Optional[int] = None
    quota_weekly: Optional[int] = None
    sync_enabled: Optional[bool] = None
    sync_interval: Optional[int] = None


class ProviderResponse(BaseModel):
    """供应商响应"""
    provider_id: str
    name: str
    type: str
    endpoint: str
    priority: int
    timeout: int
    status: str
    health_status: str
    last_check_at: Optional[datetime]
    quota_hourly: int
    quota_weekly: int
    sync_enabled: bool = False
    sync_interval: int = 300
    last_sync_at: Optional[datetime] = None

    class Config:
        from_attributes = True


class ProviderListResponse(BaseModel):
    """供应商列表响应"""
    total: int
    items: List[ProviderResponse]


# ========== 模型映射管理 ==========

class ModelMappingCreate(BaseModel):
    """创建模型映射请求"""
    model_id: str
    display_name: Optional[str] = None
    provider_id: str
    provider_model: str
    aliases: Optional[str] = None
    status: str = "active"


class ModelMappingUpdate(BaseModel):
    """更新模型映射请求"""
    display_name: Optional[str] = None
    provider_id: Optional[str] = None
    provider_model: Optional[str] = None
    aliases: Optional[str] = None
    status: Optional[str] = None


class ModelMappingResponse(BaseModel):
    """模型映射响应"""
    model_id: str
    display_name: Optional[str]
    provider_id: str
    provider_model: str
    aliases: Optional[str]
    status: str

    class Config:
        from_attributes = True


class ModelMappingListResponse(BaseModel):
    """模型映射列表响应"""
    total: int
    items: List[ModelMappingResponse]
