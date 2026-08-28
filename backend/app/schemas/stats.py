"""
用量统计相关Schema
"""
from pydantic import BaseModel
from typing import List, Optional


class UsageStats(BaseModel):
    """用量统计响应"""
    total_tokens: int = 0
    total_requests: int = 0
    avg_latency_ms: int = 0
    success_rate: float = 100.0


class ModelUsage(BaseModel):
    """模型使用统计"""
    model: str
    tokens: int
    requests: int
    cost: float = 0.0


class DailyUsage(BaseModel):
    """每日使用统计"""
    date: str
    tokens: int
    requests: int


class UsageStatsResponse(UsageStats):
    """完整用量统计响应"""
    by_model: List[ModelUsage] = []
    by_day: List[DailyUsage] = []


class UsageQuery(BaseModel):
    """用量查询参数"""
    start_date: Optional[str] = None
    end_date: Optional[str] = None
    model: Optional[str] = None
