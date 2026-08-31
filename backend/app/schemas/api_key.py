"""
API Key相关Schema
"""
from pydantic import BaseModel, Field
from typing import Optional, List
from datetime import datetime


class ApiKeyBase(BaseModel):
    """API Key基础字段"""
    name: str = Field(
        validation_alias='key_name',  # 接收时用 key_name
        serialization_alias='name'      # 返回时用 name
    )
    daily_limit: int = 0
    monthly_limit: int = 0
    qps_limit: int = 10
    
    model_config = {'populate_by_name': True}


class ApiKeyCreate(BaseModel):
    """创建API Key请求"""
    name: str = Field(
        validation_alias='key_name',  # 接收 name 或 key_name
        serialization_alias='name'      # 返回 name
    )
    daily_limit: int = 0
    monthly_limit: int = 0
    qps_limit: int = 10
    model_group_ids: Optional[List[str]] = None

    model_config = {'populate_by_name': True}


class ApiKeyUpdate(BaseModel):
    """更新API Key请求"""
    name: Optional[str] = Field(
        default=None,
        validation_alias='key_name',  # 接收 name 或 key_name
        serialization_alias='name'      # 返回 name
    )
    daily_limit: Optional[int] = None
    monthly_limit: Optional[int] = None
    qps_limit: Optional[int] = None
    ip_whitelist: Optional[List[str]] = None
    model_group_ids: Optional[List[str]] = None

    model_config = {'populate_by_name': True}


class ApiKeyResponse(BaseModel):
    """API Key响应"""
    key_id: str
    user_id: str
    api_key: str
    name: str = Field(
        validation_alias='key_name',  # 接收时用 key_name
        serialization_alias='name'      # 返回时用 name
    )
    daily_limit: int
    daily_used: int
    monthly_limit: int
    monthly_used: int
    qps_limit: int
    status: str
    created_at: datetime
    last_used_at: Optional[datetime] = None
    model_groups: List[str] = []

    model_config = {'populate_by_name': True}


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
    name: str = Field(
        validation_alias='key_name',  # 接收时用 key_name
        serialization_alias='name'      # 返回时用 name
    )
    
    model_config = {'populate_by_name': True}
