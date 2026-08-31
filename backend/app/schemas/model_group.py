"""
模型分组Schema
"""
from pydantic import BaseModel, Field
from typing import Optional, List
from datetime import datetime


class ModelGroupBase(BaseModel):
    """模型分组基础字段"""
    name: str
    description: Optional[str] = None
    is_default: int = 0


class ModelGroupCreate(ModelGroupBase):
    """创建模型分组请求"""
    provider_ids: Optional[List[str]] = None


class ModelGroupUpdate(BaseModel):
    """更新模型分组请求"""
    name: Optional[str] = None
    description: Optional[str] = None
    status: Optional[str] = None
    is_default: Optional[int] = None
    provider_ids: Optional[List[str]] = None


class ModelGroupResponse(ModelGroupBase):
    """模型分组响应"""
    group_id: str
    status: str
    provider_ids: List[str] = []
    created_at: datetime

    class Config:
        from_attributes = True


class ModelGroupListResponse(BaseModel):
    """模型分组列表响应"""
    total: int
    items: List[ModelGroupResponse]
