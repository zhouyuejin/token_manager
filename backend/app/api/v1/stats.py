"""
用量统计接口
"""
from datetime import datetime, timedelta
from typing import Optional
from sqlalchemy import case, func, and_

from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.models.user import User
from app.models.api_key import ApiKey
from app.models.usage_log import UsageLog
from app.models.model import Model as ModelMapping, ModelStatus as ModelMappingStatus
from app.models.model_channel import ModelChannel
from app.models.budget import Budget
from app.models.project import Project
from app.models.organization import Department
from app.models.quota_reservation import QuotaReservation
from app.models.channel import Channel
from app.dependencies import get_current_user
from app.schemas.stats import UsageStatsResponse, ModelUsage, DailyUsage
from app.services.budget_service import BudgetService, current_month

router = APIRouter()


@router.get("/usage", response_model=UsageStatsResponse)
async def get_usage_stats(
    start_date: Optional[str] = Query(None, description="开始日期 YYYY-MM-DD"),
    end_date: Optional[str] = Query(None, description="结束日期 YYYY-MM-DD"),
    department_id: Optional[str] = Query(None),
    project_id: Optional[str] = Query(None),
    key_id: Optional[str] = Query(None),
    model: Optional[str] = Query(None),
    channel_id: Optional[str] = Query(None),
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
    filters = [UsageLog.user_id == user_id, func.date(UsageLog.created_at) >= start_date,
               func.date(UsageLog.created_at) <= end_date]
    for column, value in ((UsageLog.department_id, department_id), (UsageLog.project_id, project_id), (UsageLog.key_id, key_id),
                          (UsageLog.model, model), (UsageLog.channel_id, channel_id)):
        if value:
            filters.append(column == value)
    query = db.query(UsageLog).filter(and_(*filters))
    
    # 基础统计
    total_tokens = db.query(func.sum(UsageLog.total_tokens)).filter(and_(*filters)).scalar() or 0
    
    total_requests = query.count()
    
    # 平均延迟
    avg_latency = db.query(func.avg(UsageLog.latency_ms)).filter(and_(*filters)).scalar() or 0
    
    # 成功率
    success_count = query.filter(UsageLog.status_code == 200).count()
    success_rate = (success_count / total_requests * 100) if total_requests > 0 else 100.0
    
    # 按模型统计（包含输入/输出token分别统计，用于计算成本）
    model_stats = db.query(
        UsageLog.model,
        func.sum(UsageLog.total_tokens).label('tokens'),
        func.sum(case((UsageLog.cost_usd.is_(None), UsageLog.prompt_tokens), else_=0)).label('prompt_tokens'),
        func.sum(case((UsageLog.cost_usd.is_(None), UsageLog.completion_tokens), else_=0)).label('completion_tokens'),
        func.sum(UsageLog.cost_usd).label('saved_cost'),
        func.count(UsageLog.id).label('requests')
    ).filter(and_(*filters)).group_by(UsageLog.model).all()
    
    # 获取模型显示名称和价格
    # UsageLog.model 存储的是 upstream_model，需要通过 ModelChannel 映射到 model_id
    upstream_models = [stat.model for stat in model_stats]
    
    # 先通过 ModelChannel 获取 upstream_model -> model_id 的映射
    upstream_to_model_id = {}
    if upstream_models:
        channel_mappings = db.query(
            ModelChannel.upstream_model,
            ModelChannel.model_id
        ).filter(
            ModelChannel.upstream_model.in_(upstream_models)
        ).all()
        upstream_to_model_id = {up: mid for up, mid in channel_mappings}
    
    # 获取所有需要查询的 model_id
    target_model_ids = list(set(upstream_to_model_id.values()) | set(upstream_models))
    
    model_mappings = []
    if target_model_ids:
        model_mappings = db.query(
            ModelMapping.model_id, 
            ModelMapping.display_name,
            ModelMapping.price_per_1k_input,
            ModelMapping.price_per_1k_output
        ).filter(
            ModelMapping.model_id.in_(target_model_ids)
        ).all()
    model_info_map = {m.model_id: m for m in model_mappings}
    
    by_model = []
    total_cost = 0.0
    for stat in model_stats:
        # 通过 upstream_model 找到对应的 model_id，再找到模型信息
        internal_model_id = stat.model if stat.model in model_info_map else upstream_to_model_id.get(stat.model)
        model_info = model_info_map.get(internal_model_id) if internal_model_id else None
        # 计算成本：(输入token数/1000)*输入单价 + (输出token数/1000)*输出单价
        if model_info:
            input_price = float(model_info.price_per_1k_input) if model_info.price_per_1k_input is not None else 0
            output_price = float(model_info.price_per_1k_output) if model_info.price_per_1k_output is not None else 0
            prompt_tokens = float(stat.prompt_tokens) if stat.prompt_tokens else 0
            completion_tokens = float(stat.completion_tokens) if stat.completion_tokens else 0
            input_cost = prompt_tokens / 1000 * input_price
            output_cost = completion_tokens / 1000 * output_price
            cost = input_cost + output_cost
        else:
            cost = 0.0
        
        cost += float(stat.saved_cost or 0)
        total_cost += cost
        by_model.append(ModelUsage(
            model=(model_info.display_name or stat.model) if model_info else stat.model,
            tokens=stat.tokens or 0,
            requests=stat.requests,
            cost=round(cost, 4)
        ))
    
    # 按日期统计
    day_stats = db.query(
        func.date(UsageLog.created_at).label('date'),
        func.sum(UsageLog.total_tokens).label('tokens'),
        func.count(UsageLog.id).label('requests')
    ).filter(and_(*filters)).group_by(func.date(UsageLog.created_at)).order_by(func.date(UsageLog.created_at)).all()
    
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
        total_cost=round(total_cost, 8),
        by_model=by_model,
        by_day=by_day
    )


@router.get('/billing')
async def get_my_billing(current_user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    """用户只能查看自己 Key 归属项目的当月预算和未结预扣。"""
    keys = db.query(ApiKey).filter(ApiKey.user_id == current_user.user_id).all()
    project_ids = {row.project_id for row in keys if row.project_id}
    projects = db.query(Project).filter(Project.project_id.in_(project_ids)).all() if project_ids else []
    department_ids = {row.dept_id for row in projects if row.dept_id}
    month = current_month()
    budgets = db.query(Budget).filter(Budget.month == month, Budget.enabled.is_(True),
        ((Budget.scope_type == 'project') & Budget.scope_id.in_(project_ids)) |
        ((Budget.scope_type == 'department') & Budget.scope_id.in_(department_ids))).all() if project_ids else []
    names = {row.project_id: row.name for row in projects}
    names.update({row.dept_id: row.name for row in db.query(Department).filter(Department.dept_id.in_(department_ids)).all()})
    service = BudgetService(db)
    reservations = db.query(QuotaReservation).filter_by(user_id=current_user.user_id, status='reserved').order_by(
        QuotaReservation.created_at.desc()).all()
    return {
        'month': month,
        'budgets': [{**{field: getattr(row, field) for field in ('budget_id', 'scope_type', 'scope_id', 'amount_usd', 'policy')},
                     'scope_name': names.get(row.scope_id, row.scope_id), **service.summary(row)} for row in budgets],
        'reservations': [{field: getattr(row, field) for field in ('reservation_id', 'key_id', 'project_id', 'model',
                         'estimated_tokens', 'estimated_cost_usd', 'status', 'created_at', 'expires_at')} for row in reservations],
    }


@router.get('/options')
async def get_my_usage_options(current_user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    keys = db.query(ApiKey).filter(ApiKey.user_id == current_user.user_id).all()
    project_ids = {row.project_id for row in keys if row.project_id}
    projects = db.query(Project).filter(Project.project_id.in_(project_ids)).all() if project_ids else []
    department_ids = {row.dept_id for row in projects}
    departments = db.query(Department).filter(Department.dept_id.in_(department_ids)).all() if department_ids else []
    models = [row[0] for row in db.query(UsageLog.model).filter_by(user_id=current_user.user_id).distinct().all()]
    channel_ids = [row[0] for row in db.query(UsageLog.channel_id).filter(
        UsageLog.user_id == current_user.user_id, UsageLog.channel_id.is_not(None)).distinct().all()]
    channel_names = {row.channel_id: row.name for row in db.query(Channel).filter(Channel.channel_id.in_(channel_ids)).all()} if channel_ids else {}
    return {
        'keys': [{'key_id': row.key_id, 'name': row.key_name, 'project_id': row.project_id} for row in keys],
        'projects': [{'project_id': row.project_id, 'name': row.name, 'department_id': row.dept_id} for row in projects],
        'departments': [{'department_id': row.dept_id, 'name': row.name} for row in departments],
        'models': models,
        'channels': [{'channel_id': value, 'name': channel_names.get(value, value)} for value in channel_ids],
    }


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
