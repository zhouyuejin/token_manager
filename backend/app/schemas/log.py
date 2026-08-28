"""
日志查询相关Schema
"""
from pydantic import BaseModel
from typing import Optional, List, Any
from datetime import datetime


class OperationLogResponse(BaseModel):
    """操作日志响应"""
    log_id: str
    operator_id: str
    operator_name: str
    action: str
    target_type: str
    target_id: Optional[str] = None
    detail: Optional[Any] = None
    ip_address: Optional[str] = None
    created_at: datetime

    model_config = {"from_attributes": True}


class OperationLogListResponse(BaseModel):
    """操作日志列表响应"""
    total: int
    items: List[OperationLogResponse]


class LoginLogResponse(BaseModel):
    """登录日志响应"""
    log_id: str
    username: str
    user_id: Optional[str] = None
    ip_address: Optional[str] = None
    user_agent: Optional[str] = None
    status: str
    failure_reason: Optional[str] = None
    created_at: datetime

    model_config = {"from_attributes": True}


class LoginLogListResponse(BaseModel):
    """登录日志列表响应"""
    total: int
    items: List[LoginLogResponse]
