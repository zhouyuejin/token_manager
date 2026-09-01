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
from app.models.model_mapping import ModelMapping
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
    
    # 按模型统计（包含输入/输出token分别统计，用于计算成本）
    model_stats = db.query(
        UsageLog.model,
        func.sum(UsageLog.total_tokens).label('tokens'),
        func.sum(UsageLog.prompt_tokens).label('prompt_tokens'),
        func.sum(UsageLog.completion_tokens).label('completion_tokens'),
        func.count(UsageLog.id).label('requests')
    ).filter(
        and_(
            UsageLog.user_id == user_id,
            func.date(UsageLog.created_at) >= start_date,
            func.date(UsageLog.created_at) <= end_date
        )
    ).group_by(UsageLog.model).all()
    
    # 获取模型显示名称和价格
    model_ids = [stat.model for stat in model_stats]
    model_mappings = []
    if model_ids:
        model_mappings = db.query(
            ModelMapping.model_id, 
            ModelMapping.display_name,
            ModelMapping.price_per_1k_input,
            ModelMapping.price_per_1k_output
        ).filter(
            ModelMapping.model_id.in_(model_ids)
        ).all()
    model_info_map = {m.model_id: m for m in model_mappings}
    
    by_model = []
    for stat in model_stats:
        model_info = model_info_map.get(stat.model)
        # 计算成本：(输入token数/1000)*输入单价 + (输出token数/1000)*输出单价
        if model_info:
            # 检查价格是否存在（不为 None）
            input_price = float(model_info.price_per_1k_input) if model_info.price_per_1k_input is not None else 0
            output_price = float(model_info.price_per_1k_output) if model_info.price_per_1k_output is not None else 0
            # 将 Decimal 转换为 float
            prompt_tokens = float(stat.prompt_tokens) if stat.prompt_tokens else 0
            completion_tokens = float(stat.completion_tokens) if stat.completion_tokens else 0
            input_cost = prompt_tokens / 1000 * input_price
            output_cost = completion_tokens / 1000 * output_price
            cost = input_cost + output_cost
        else:
            cost = 0.0
        
        by_model.append(ModelUsage(
            model=model_info.display_name if model_info else stat.model,
            tokens=stat.tokens or 0,
            requests=stat.requests,
            cost=round(cost, 4)
        ))
    
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
