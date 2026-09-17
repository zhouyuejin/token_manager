"""
API Key相关Schema

Task 5: 删除所有 model_group_ids / model_groups 字段。
API Key 不再保留独立分组权限，统一由用户分组决定。
GC-9: per-key 额度完全移除。daily_limit / monthly_limit 不再是 ApiKey 的字段。
Phase 1.3: API Key 保留限流字段（QPS/RPM/TPM/并发），额度仍由 User.quota 负责。
"""
from pydantic import BaseModel, Field, field_validator
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
    project_id: str = Field(min_length=1, max_length=32)
    ip_whitelist: Optional[List[str]] = None
    expires_at: Optional[datetime] = None
    qps_limit: int = Field(default=0, ge=0)
    rpm_limit: int = Field(default=0, ge=0)
    tpm_limit: int = Field(default=0, ge=0)
    concurrency_limit: int = Field(default=0, ge=0)
    # NO model_group_ids — API Key 权限统一由用户分组决定

    model_config = {'populate_by_name': True}


class ApiKeyUpdate(BaseModel):
    """更新API Key请求（用户）"""
    name: Optional[str] = Field(
        default=None,
        validation_alias='key_name',
        serialization_alias='name'
    )
    project_id: Optional[str] = Field(default=None, min_length=1, max_length=32)
    ip_whitelist: Optional[List[str]] = None
    expires_at: Optional[datetime] = None
    qps_limit: Optional[int] = Field(default=None, ge=0)
    rpm_limit: Optional[int] = Field(default=None, ge=0)
    tpm_limit: Optional[int] = Field(default=None, ge=0)
    concurrency_limit: Optional[int] = Field(default=None, ge=0)
    # NO model_group_ids — API Key 权限统一由用户分组决定

    @field_validator("project_id")
    @classmethod
    def reject_empty_project(cls, value):
        if value is None or not value.strip():
            raise ValueError("项目不能为空")
        return value

    model_config = {'populate_by_name': True}


class ApiKeyResponse(BaseModel):
    """API Key响应（用户）"""
    project_id: Optional[str] = None
    project_name: Optional[str] = None
    department_id: Optional[str] = None
    department_name: Optional[str] = None
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
    ip_whitelist: List[str] = []
    expires_at: Optional[UtcDateTime] = None
    revoked_at: Optional[UtcDateTime] = None
    revoked_reason: Optional[str] = None
    frozen_at: Optional[UtcDateTime] = None
    frozen_reason: Optional[str] = None
    last_used_ip: Optional[str] = None
    last_used_user_agent: Optional[str] = None
    qps_limit: int = Field(default=0, ge=0)
    rpm_limit: int = Field(default=0, ge=0)
    tpm_limit: int = Field(default=0, ge=0)
    concurrency_limit: int = Field(default=0, ge=0)
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
    project_id: Optional[str] = None
    project_name: Optional[str] = None
    department_id: Optional[str] = None
    department_name: Optional[str] = None
    key_id: str
    api_key: str
    name: str = Field(
        validation_alias='key_name',
        serialization_alias='name'
    )
    expires_at: Optional[UtcDateTime] = None
    qps_limit: int = Field(default=0, ge=0)
    rpm_limit: int = Field(default=0, ge=0)
    tpm_limit: int = Field(default=0, ge=0)
    concurrency_limit: int = Field(default=0, ge=0)

    model_config = {'populate_by_name': True}


class ApiKeyRevokeRequest(BaseModel):
    """吊销 API Key 请求"""
    reason: Optional[str] = None


# ---------- Admin-facing schemas ----------

class ApiKeyAdminCreate(BaseModel):
    """创建API Key请求（管理员）"""
    user_id: Optional[str] = None  # admin can create for another user
    name: str = Field(
        validation_alias='key_name',
        serialization_alias='name'
    )
    project_id: str = Field(min_length=1, max_length=32)
    ip_whitelist: Optional[List[str]] = None
    expires_at: Optional[datetime] = None
    qps_limit: int = Field(default=0, ge=0)
    rpm_limit: int = Field(default=0, ge=0)
    tpm_limit: int = Field(default=0, ge=0)
    concurrency_limit: int = Field(default=0, ge=0)
    # NO model_group_ids — API Key 权限统一由用户分组决定

    model_config = {'populate_by_name': True}


class ApiKeyAdminUpdate(BaseModel):
    """更新API Key请求（管理员）"""
    name: Optional[str] = Field(
        default=None,
        validation_alias='key_name',
        serialization_alias='name'
    )
    project_id: Optional[str] = Field(default=None, min_length=1, max_length=32)
    ip_whitelist: Optional[List[str]] = None
    expires_at: Optional[datetime] = None
    qps_limit: Optional[int] = Field(default=None, ge=0)
    rpm_limit: Optional[int] = Field(default=None, ge=0)
    tpm_limit: Optional[int] = Field(default=None, ge=0)
    concurrency_limit: Optional[int] = Field(default=None, ge=0)
    # NO model_group_ids — API Key 权限统一由用户分组决定

    @field_validator("project_id")
    @classmethod
    def reject_empty_project(cls, value):
        if value is None or not value.strip():
            raise ValueError("项目不能为空")
        return value

    model_config = {'populate_by_name': True}


class ApiKeyAdminResponse(BaseModel):
    """API Key响应（管理员）"""
    project_id: Optional[str] = None
    project_name: Optional[str] = None
    department_id: Optional[str] = None
    department_name: Optional[str] = None
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
    ip_whitelist: List[str] = []
    expires_at: Optional[UtcDateTime] = None
    revoked_at: Optional[UtcDateTime] = None
    revoked_reason: Optional[str] = None
    frozen_at: Optional[UtcDateTime] = None
    frozen_reason: Optional[str] = None
    last_used_ip: Optional[str] = None
    last_used_user_agent: Optional[str] = None
    qps_limit: int = Field(default=0, ge=0)
    rpm_limit: int = Field(default=0, ge=0)
    tpm_limit: int = Field(default=0, ge=0)
    concurrency_limit: int = Field(default=0, ge=0)
    # NO model_groups — API Key 权限统一由用户分组决定

    model_config = {'populate_by_name': True}


class ApiKeyAdminListResponse(BaseModel):
    """API Key列表响应（管理员）"""
    total: int
    items: List[ApiKeyAdminResponse]
