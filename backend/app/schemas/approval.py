"""Approval API schemas."""
from pydantic import BaseModel, Field, StrictInt, field_validator
from datetime import datetime
from typing import Optional


class ApiKeyApplicationCreate(BaseModel):
    project_id: str = Field(min_length=1, max_length=32)
    name: str = Field(min_length=1, max_length=100)
    ip_whitelist: list[str] = Field(default_factory=list)
    expires_at: Optional[datetime] = None
    reason: str = Field(min_length=1, max_length=1000)

    @field_validator('project_id', 'name', 'reason')
    @classmethod
    def values_must_contain_text(cls, value):
        value = value.strip()
        if not value:
            raise ValueError('申请内容不能为空')
        return value


class QuotaApplicationCreate(BaseModel):
    amount: StrictInt = Field(gt=0)
    reason: str = Field(min_length=1, max_length=1000)

    @field_validator('reason')
    @classmethod
    def reason_must_contain_text(cls, value):
        if not value.strip():
            raise ValueError('申请理由不能为空')
        return value.strip()


class ModelGroupApplicationCreate(BaseModel):
    group_id: str = Field(min_length=1, max_length=32)
    reason: str = Field(min_length=1, max_length=1000)

    @field_validator('group_id', 'reason')
    @classmethod
    def values_must_contain_text(cls, value):
        if not value.strip():
            raise ValueError('申请内容不能为空')
        return value.strip()


class ProjectAccessApplicationCreate(BaseModel):
    project_id: str = Field(min_length=1, max_length=32)
    reason: str = Field(min_length=1, max_length=1000)

    @field_validator('project_id', 'reason')
    @classmethod
    def values_must_contain_text(cls, value):
        value = value.strip()
        if not value:
            raise ValueError('申请内容不能为空')
        return value


class ApprovalDecision(BaseModel):
    decision: str
    comment: str = Field(min_length=1, max_length=1000)

    @field_validator('comment')
    @classmethod
    def comment_must_contain_text(cls, value):
        if not value.strip():
            raise ValueError('审批意见不能为空')
        return value.strip()


class ApprovalSupplement(BaseModel):
    content: str = Field(min_length=1, max_length=1000)

    @field_validator('content')
    @classmethod
    def content_must_contain_text(cls, value):
        if not value.strip():
            raise ValueError('补充说明不能为空')
        return value.strip()
