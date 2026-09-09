"""
API Key相关Schema

Task 5: 删除所有 model_group_ids / model_groups 字段。
API Key 不再保留独立分组权限，统一由用户分组决定。
GC-9: per-key 限额完全移除。daily_limit / monthly_limit / qps_limit 不再是 ApiKey 的字段。
限流由 User.quota (USD) 单一来源负责（见 proxy_service.check_quota）。
"""
from pydantic import BaseModel, Field
from typing import Optional, List
from datetime import datetime
from app.schemas._datetime import UtcDateTime


# ---------- User-facing schemas ----------

class ApiKeyCreate(BaseModel):
    """创建API Key请求（用户）"""
    name: str = Field(
        validation_alias='key_name',
        serialization_alias='name'
    )
    # NO model_group_ids — API Key 权限统一由用户分组决定

    model_config = {'populate_by_name': True}


class ApiKeyUpdate(BaseModel):
    """更新API Key请求（用户）"""
    name: Optional[str] = Field(
        default=None,
        validation_alias='key_name',
        serialization_alias='name'
    )
    ip_whitelist: Optional[List[str]] = None
    # NO model_group_ids — API Key 权限统一由用户分组决定

    model_config = {'populate_by_name': True}


class ApiKeyResponse(BaseModel):
    """API Key响应（用户）"""
    key_id: str
    user_id: str
    api_key: str
    name: str = Field(
        validation_alias='key_name',
        serialization_alias='name'
    )
    status: str
    created_at: UtcDateTime
    last_used_at: Optional[UtcDateTime] = None
    # NO model_groups — GC-2

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
        validation_alias='key_name',
        serialization_alias='name'
    )

    model_config = {'populate_by_name': True}


# ---------- Admin-facing schemas ----------

class ApiKeyAdminCreate(BaseModel):
    """创建API Key请求（管理员）"""
    user_id: Optional[str] = None  # admin can create for another user
    name: str = Field(
        validation_alias='key_name',
        serialization_alias='name'
    )
    # NO model_group_ids — API Key 权限统一由用户分组决定

    model_config = {'populate_by_name': True}


class ApiKeyAdminUpdate(BaseModel):
    """更新API Key请求（管理员）"""
    name: Optional[str] = Field(
        default=None,
        validation_alias='key_name',
        serialization_alias='name'
    )
    ip_whitelist: Optional[List[str]] = None
    # NO model_group_ids — API Key 权限统一由用户分组决定

    model_config = {'populate_by_name': True}


class ApiKeyAdminResponse(BaseModel):
    """API Key响应（管理员）"""
    key_id: str
    user_id: str
    api_key: str
    name: str = Field(
        validation_alias='key_name',
        serialization_alias='name'
    )
    status: str
    created_at: UtcDateTime
    last_used_at: Optional[UtcDateTime] = None
    # NO model_groups — API Key 权限统一由用户分组决定

    model_config = {'populate_by_name': True}


class ApiKeyAdminListResponse(BaseModel):
    """API Key列表响应（管理员）"""
    total: int
    items: List[ApiKeyAdminResponse]
