"""
用量统计接口
"""
from datetime import datetime, timedelta
from typing import Optional
from sqlalchemy import func, and_

from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.models.user import User
from app.models.api_key import ApiKey
from app.models.usage_log import UsageLog
from app.dependencies import get_current_user
from app.schemas.stats import UsageStatsResponse, ModelUsage, DailyUsage

router = APIRouter()


@router.get("/usage", response_model=UsageStatsResponse)
async def get_usage_stats(
    start_date: Optional[str] = Query(None, description="开始日期 YYYY-MM-DD"),
    end_date: Optional[str] = Query(None, description="结束日期 YYYY-MM-DD"),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    获取用量统计
    """
    # 默认查询最近7天
    if not end_date:
        end_date = datetime.now().strftime("%Y-%m-%d")
    if not start_date:
        start_date = (datetime.now() - timedelta(days=7)).strftime("%Y-%m-%d")
    
    # 查询条件
    user_id = current_user.user_id
    
    # 用量日志查询
    query = db.query(UsageLog).filter(
        and_(
            UsageLog.user_id == user_id,
            func.date(UsageLog.created_at) >= start_date,
            func.date(UsageLog.created_at) <= end_date
        )
    )
    
    # 基础统计
    total_tokens = db.query(func.sum(UsageLog.total_tokens)).filter(
        and_(
            UsageLog.user_id == user_id,
            func.date(UsageLog.created_at) >= start_date,
            func.date(UsageLog.created_at) <= end_date
        )
    ).scalar() or 0
    
    total_requests = query.count()
    
    # 平均延迟
    avg_latency = db.query(func.avg(UsageLog.latency_ms)).filter(
        and_(
            UsageLog.user_id == user_id,
            func.date(UsageLog.created_at) >= start_date,
            func.date(UsageLog.created_at) <= end_date
        )
    ).scalar() or 0
    
    # 成功率
    success_count = query.filter(UsageLog.status_code == 200).count()
    success_rate = (success_count / total_requests * 100) if total_requests > 0 else 100.0
    
    # 按模型统计
    model_stats = db.query(
        UsageLog.model,
        func.sum(UsageLog.total_tokens).label('tokens'),
        func.count(UsageLog.id).label('requests')
    ).filter(
        and_(
            UsageLog.user_id == user_id,
            func.date(UsageLog.created_at) >= start_date,
            func.date(UsageLog.created_at) <= end_date
        )
    ).group_by(UsageLog.model).all()
    
    by_model = [
        ModelUsage(
            model=stat.model,
            tokens=stat.tokens or 0,
            requests=stat.requests,
            cost=0.0  # TODO: 根据模型单价计算
        )
        for stat in model_stats
    ]
    
    # 按日期统计
    day_stats = db.query(
        func.date(UsageLog.created_at).label('date'),
        func.sum(UsageLog.total_tokens).label('tokens'),
        func.count(UsageLog.id).label('requests')
    ).filter(
        and_(
            UsageLog.user_id == user_id,
            func.date(UsageLog.created_at) >= start_date,
            func.date(UsageLog.created_at) <= end_date
        )
    ).group_by(func.date(UsageLog.created_at)).order_by(func.date(UsageLog.created_at)).all()
    
    by_day = [
        DailyUsage(
            date=stat.date.strftime("%Y-%m-%d") if isinstance(stat.date, datetime) else str(stat.date),
            tokens=stat.tokens or 0,
            requests=stat.requests
        )
        for stat in day_stats
    ]
    
    return UsageStatsResponse(
        total_tokens=total_tokens,
        total_requests=total_requests,
        avg_latency_ms=int(avg_latency),
        success_rate=round(success_rate, 2),
        by_model=by_model,
        by_day=by_day
    )


@router.get("/usage/by-model")
async def get_usage_by_model(
    start_date: Optional[str] = Query(None),
    end_date: Optional[str] = Query(None),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    按模型统计用量
    """
    if not end_date:
        end_date = datetime.now().strftime("%Y-%m-%d")
    if not start_date:
        start_date = (datetime.now() - timedelta(days=30)).strftime("%Y-%m-%d")
    
    model_stats = db.query(
        UsageLog.model,
        func.sum(UsageLog.total_tokens).label('tokens'),
        func.sum(UsageLog.prompt_tokens).label('prompt_tokens'),
        func.sum(UsageLog.completion_tokens).label('completion_tokens'),
        func.count(UsageLog.id).label('requests'),
        func.avg(UsageLog.latency_ms).label('avg_latency')
    ).filter(
        and_(
            UsageLog.user_id == current_user.user_id,
            func.date(UsageLog.created_at) >= start_date,
            func.date(UsageLog.created_at) <= end_date
        )
    ).group_by(UsageLog.model).all()
    
    return {
        "items": [
            {
                "model": stat.model,
                "tokens": stat.tokens or 0,
                "prompt_tokens": stat.prompt_tokens or 0,
                "completion_tokens": stat.completion_tokens or 0,
                "requests": stat.requests,
                "avg_latency": int(stat.avg_latency or 0)
            }
            for stat in model_stats
        ]
    }


@router.get("/usage/by-day")
async def get_usage_by_day(
    start_date: Optional[str] = Query(None),
    end_date: Optional[str] = Query(None),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    按日期统计用量
    """
    if not end_date:
        end_date = datetime.now().strftime("%Y-%m-%d")
    if not start_date:
        start_date = (datetime.now() - timedelta(days=30)).strftime("%Y-%m-%d")
    
    day_stats = db.query(
        func.date(UsageLog.created_at).label('date'),
        func.sum(UsageLog.total_tokens).label('tokens'),
        func.count(UsageLog.id).label('requests')
    ).filter(
        and_(
            UsageLog.user_id == current_user.user_id,
            func.date(UsageLog.created_at) >= start_date,
            func.date(UsageLog.created_at) <= end_date
        )
    ).group_by(func.date(UsageLog.created_at)).order_by(func.date(UsageLog.created_at)).all()
    
    return {
        "items": [
            {
                "date": stat.date.strftime("%Y-%m-%d") if isinstance(stat.date, datetime) else str(stat.date),
                "tokens": stat.tokens or 0,
                "requests": stat.requests
            }
            for stat in day_stats
        ]
    }
