"""
用量统计接口
"""
from fastapi import APIRouter, Depends

router = APIRouter()


@router.get("/usage")
async def get_usage_stats():
    """获取用量统计"""
    # TODO: 实现
    return {
        "total_tokens": 1250000,
        "total_requests": 3500,
        "avg_latency_ms": 1500
    }
