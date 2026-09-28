"""Approval API schemas."""
from pydantic import BaseModel, Field, StrictInt, field_validator


class QuotaApplicationCreate(BaseModel):
    amount: StrictInt = Field(gt=0)
    reason: str = Field(min_length=1, max_length=1000)

    @field_validator('reason')
    @classmethod
    def reason_must_contain_text(cls, value):
        if not value.strip():
            raise ValueError('申请理由不能为空')
        return value.strip()


class ApprovalDecision(BaseModel):
    decision: str
    comment: str | None = Field(default=None, max_length=1000)
