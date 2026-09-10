"""
管理后台接口

Channel (渠道) 和 Model (模型) 管理
"""
import secrets
import asyncio
import json
from typing import Optional, List, Any
from datetime import datetime, timezone, timedelta
from sqlalchemy import func, and_
from fastapi import APIRouter, Depends, HTTPException, status, Query, Request, Response
from fastapi.responses import RedirectResponse
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.models.user import User, UserRole, UserStatus
from app.models.channel import Channel, ChannelType, ChannelStatus, ChannelHealthStatus
from app.models.channel_quota import ChannelQuota, QuotaType, SyncStatus
from app.models.model import Model, ModelStatus, PriceType
from app.models.model_channel import ModelChannel
from app.models.usage_log import UsageLog
from app.dependencies import get_current_user, require_admin
from app.schemas.admin import (
    AdminStatsResponse,
    AdminUserCreate, AdminUserUpdate, AdminUserResponse,
    UserListResponse, QuotaAdjustRequest,
    ChannelCreate, ChannelUpdate, ChannelResponse, ChannelListResponse,
    ChannelWithModelsResponse,
    ChannelQuotaResponse, ChannelQuotaListResponse, QuotaDetail,
    ChannelTestRequest, ChannelTestResponse,
    ModelCreate, ModelUpdate, ModelResponse, ModelListResponse,
    ModelWithChannelsResponse, ModelChannelCreate, ModelChannelUpdate, ModelChannelResponse,
    UserUsage, ChannelUsage, ModelUsageStats, DailyUsageStats,
)
from app.services.operation_log_service import record_operation
from app.utils.request import extract_client_ip

router = APIRouter()


def _apply_role_transition(user: "User", new_role_value: str, changed: dict) -> bool:
    """检测并应用 role transition 的自动副作用"""
    try:
        new_role = UserRole(new_role_value)
    except ValueError:
        return False

    if user.role == new_role:
        return False

    if new_role == UserRole.admin:
        user.quota = -1
        user.model_group_ids = "[]"
        changed["quota"] = -1
        changed["model_group_ids"] = []
        changed["auto"] = "promoted_to_admin"
    else:
        user.quota = 0
        user.model_group_ids = "[]"
        changed["quota"] = 0
        changed["model_group_ids"] = []
        changed["auto"] = "demoted_from_admin"

    user.role = new_role
    changed["role"] = new_role_value
    return True


# ========== 用量统计 ==========

@router.get("/stats/usage", response_model=AdminStatsResponse)
async def get_admin_usage_stats(
    start_date: Optional[str] = Query(None, description="开始日期 YYYY-MM-DD"),
    end_date: Optional[str] = Query(None, description="结束日期 YYYY-MM-DD"),
    admin: User = Depends(require_admin),
    db: Session = Depends(get_db)
):
    """获取管理员用量统计"""
    from datetime import timedelta as td
    
    if not end_date:
        end_date = datetime.now().strftime("%Y-%m-%d")
    if not start_date:
        start_date = (datetime.now() - td(days=7)).strftime("%Y-%m-%d")
    
    base_filter = and_(
        func.date(UsageLog.created_at) >= start_date,
        func.date(UsageLog.created_at) <= end_date
    )
    
    total_tokens = db.query(func.sum(UsageLog.total_tokens)).filter(base_filter).scalar() or 0
    total_requests = db.query(UsageLog).filter(base_filter).count()
    avg_latency = db.query(func.avg(UsageLog.latency_ms)).filter(base_filter).scalar() or 0
    success_count = db.query(UsageLog).filter(base_filter, UsageLog.status_code == 200).count()
    success_rate = (success_count / total_requests * 100) if total_requests > 0 else 100.0
    
    # 按用户统计
    user_stats = db.query(
        UsageLog.user_id,
        func.sum(UsageLog.total_tokens).label('tokens'),
        func.count(UsageLog.id).label('requests')
    ).filter(base_filter).group_by(UsageLog.user_id).all()
    
    user_ids = [s.user_id for s in user_stats]
    user_map = {u.user_id: u.username for u in db.query(User.user_id, User.username).filter(User.user_id.in_(user_ids)).all()} if user_ids else {}
    
    by_user = [{"user_id": s.user_id, "username": user_map.get(s.user_id, s.user_id), "tokens": s.tokens or 0, "requests": s.requests or 0} for s in user_stats] if user_stats else []
    
    # 按渠道统计
    channel_stats = db.query(
        UsageLog.channel_id,
        func.sum(UsageLog.total_tokens).label('tokens'),
        func.count(UsageLog.id).label('requests')
    ).filter(base_filter).group_by(UsageLog.channel_id).all()
    
    channel_ids = [s.channel_id for s in channel_stats if s.channel_id]
    channel_map = {c.channel_id: c.name for c in db.query(Channel.channel_id, Channel.name).filter(Channel.channel_id.in_(channel_ids)).all()} if channel_ids else {}
    
    by_channel = [{"channel": channel_map.get(s.channel_id, s.channel_id or "未知"), "tokens": s.tokens or 0, "requests": s.requests or 0} for s in channel_stats] if channel_stats else []
    
    # 按模型统计
    model_stats = db.query(
        UsageLog.model,
        func.sum(UsageLog.total_tokens).label('tokens'),
        func.sum(UsageLog.prompt_tokens).label('prompt_tokens'),
        func.sum(UsageLog.completion_tokens).label('completion_tokens'),
        func.count(UsageLog.id).label('requests')
    ).filter(base_filter).group_by(UsageLog.model).all()
    
    model_ids = [s.model for s in model_stats]
    model_info = {m.model_id: m for m in db.query(Model).filter(Model.model_id.in_(model_ids)).all()} if model_ids else {}
    
    by_model = []
    for s in model_stats:
        info = model_info.get(s.model)
        if info:
            cost = (float(s.prompt_tokens or 0) / 1000 * float(info.price_per_1k_input or 0) + 
                    float(s.completion_tokens or 0) / 1000 * float(info.price_per_1k_output or 0))
        else:
            cost = 0
        by_model.append({"model": s.model, "display_name": info.display_name if info else None, "tokens": s.tokens or 0, "requests": s.requests or 0, "cost": round(cost, 4)})
    
    # 按日统计
    daily_stats = db.query(
        func.date(UsageLog.created_at).label('date'),
        func.sum(UsageLog.total_tokens).label('tokens'),
        func.count(UsageLog.id).label('requests')
    ).filter(base_filter).group_by(func.date(UsageLog.created_at)).order_by(func.date(UsageLog.created_at)).all()
    
    by_day = [{"date": str(s.date), "tokens": s.tokens or 0, "requests": s.requests or 0} for s in daily_stats] if daily_stats else []
    
    return AdminStatsResponse(
        total_tokens=total_tokens, total_requests=total_requests,
        avg_latency_ms=round(avg_latency, 2) if avg_latency else 0,
        success_rate=round(success_rate, 2),
        by_user=by_user, by_channel=by_channel, by_model=by_model, by_day=by_day,
        by_provider=by_channel  # 兼容
    )


# ========== 用户管理 ==========

@router.get("/users", response_model=UserListResponse)
async def list_users(
    page: int = Query(1, ge=1), page_size: int = Query(20, ge=1, le=100),
    keyword: Optional[str] = None, role: Optional[str] = None, status: Optional[str] = None,
    db: Session = Depends(get_db), admin: User = Depends(require_admin)
):
    """用户列表"""
    query = db.query(User)
    if keyword:
        query = query.filter(User.username.contains(keyword) | User.email.contains(keyword))
    if role:
        query = query.filter(User.role == role)
    if status:
        query = query.filter(User.status == status)
    
    total = query.count()
    users = query.order_by(User.created_at.desc()).offset((page - 1) * page_size).limit(page_size).all()
    
    return UserListResponse(total=total, items=[AdminUserResponse(
        user_id=u.user_id, username=u.username, email=u.email, role=u.role.value if hasattr(u.role, 'value') else str(u.role),
        status=u.status.value if hasattr(u.status, 'value') else str(u.status),
        quota=u.quota, quota_used=u.quota_used, created_at=u.created_at,
        model_group_ids=json.loads(u.model_group_ids or '[]')
    ) for u in users])


@router.post("/users")
async def create_user(data: AdminUserCreate, db: Session = Depends(get_db), admin: User = Depends(require_admin)):
    """创建用户"""
    if db.query(User).filter(User.username == data.username).first():
        raise HTTPException(status_code=400, detail="用户名已存在")
    
    from app.core.security import get_password_hash
    user = User(
        user_id=f"u_{secrets.token_hex(8)}", username=data.username, email=data.email,
        password_hash=get_password_hash(data.password), role=UserRole(data.role),
        quota=data.quota, model_group_ids=json.dumps(data.model_group_ids)
    )
    db.add(user)
    db.commit()
    db.refresh(user)
    
    return AdminUserResponse(
        user_id=user.user_id, username=user.username, email=user.email,
        role=user.role.value if hasattr(user.role, 'value') else str(user.role),
        status=user.status.value if hasattr(user.status, 'value') else str(user.status),
        quota=user.quota, quota_used=user.quota_used, created_at=user.created_at,
        model_group_ids=data.model_group_ids
    )


@router.get("/users/{user_id}")
async def get_user(user_id: str, db: Session = Depends(get_db), admin: User = Depends(require_admin)):
    """获取用户"""
    user = db.query(User).filter(User.user_id == user_id).first()
    if not user:
        raise HTTPException(status_code=404, detail="用户不存在")
    
    return AdminUserResponse(
        user_id=user.user_id, username=user.username, email=user.email,
        role=user.role.value if hasattr(user.role, 'value') else str(user.role),
        status=user.status.value if hasattr(user.status, 'value') else str(user.status),
        quota=user.quota, quota_used=user.quota_used, created_at=user.created_at,
        model_group_ids=json.loads(user.model_group_ids or '[]')
    )


@router.put("/users/{user_id}")
async def update_user(user_id: str, data: AdminUserUpdate, request: Request, db: Session = Depends(get_db), admin: User = Depends(require_admin)):
    """更新用户"""
    user = db.query(User).filter(User.user_id == user_id).first()
    if not user:
        raise HTTPException(status_code=404, detail="用户不存在")
    
    changed = {}
    for field, value in data.model_dump(exclude_unset=True).items():
        if field == "model_group_ids" and value is not None:
            value = json.dumps(value)
        if getattr(user, field) != value:
            changed[field] = value
            setattr(user, field, value)
    
    if _apply_role_transition(user, data.role, changed):
        pass  # role transition 已修改 changed
    
    db.commit()
    
    record_operation(db=db, operator=admin, action="update", target_type="user", target_id=user_id, detail=changed, ip_address=extract_client_ip(request))
    return {"message": "更新成功"}


@router.delete("/users/{user_id}")
async def delete_user(user_id: str, request: Request, db: Session = Depends(get_db), admin: User = Depends(require_admin)):
    """删除用户"""
    user = db.query(User).filter(User.user_id == user_id).first()
    if not user:
        raise HTTPException(status_code=404, detail="用户不存在")
    if user.role == UserRole.admin:
        raise HTTPException(status_code=400, detail="不能删除管理员账户")
    
    db.delete(user)
    db.commit()
    record_operation(db=db, operator=admin, action="delete", target_type="user", target_id=user_id, detail={}, ip_address=extract_client_ip(request))
    return {"message": "删除成功"}


@router.post("/users/{user_id}/quota")
async def adjust_quota(user_id: str, data: QuotaAdjustRequest, request: Request, db: Session = Depends(get_db), admin: User = Depends(require_admin)):
    """调整用户额度"""
    user = db.query(User).filter(User.user_id == user_id).first()
    if not user:
        raise HTTPException(status_code=404, detail="用户不存在")
    
    if data.set_unlimited:
        user.quota = -1
        detail = {"quota": -1, "reason": data.reason, "action": "set_unlimited"}
    elif data.amount is not None:
        if user.quota < 0:
            user.quota = data.amount
        else:
            user.quota = data.amount
        detail = {"quota": data.amount, "reason": data.reason, "action": "set"}
    else:
        raise HTTPException(status_code=400, detail="参数错误")
    
    db.commit()
    record_operation(db=db, operator=admin, action="adjust_quota", target_type="user", target_id=user_id, detail=detail, ip_address=extract_client_ip(request))
    return {"message": "额度调整成功"}


# ========== 渠道管理 (Channel) ==========

@router.get("/channels", response_model=ChannelListResponse)
async def list_channels(
    page: int = Query(1, ge=1), page_size: int = Query(20, ge=1, le=100),
    keyword: Optional[str] = None, status: Optional[str] = None,
    db: Session = Depends(get_db), admin: User = Depends(require_admin)
):
    """渠道列表"""
    query = db.query(Channel)
    if keyword:
        query = query.filter(Channel.name.contains(keyword) | Channel.channel_id.contains(keyword))
    if status:
        query = query.filter(Channel.status == status)
    
    total = query.count()
    channels = query.order_by(Channel.priority.desc(), Channel.created_at.desc()).offset((page - 1) * page_size).limit(page_size).all()
    
    items = []
    for ch in channels:
        bound_count = db.query(ModelChannel).filter(ModelChannel.channel_id == ch.channel_id).count()
        extra_keys = json.loads(ch.extra_keys) if ch.extra_keys else None
        items.append(ChannelResponse(
            channel_id=ch.channel_id, name=ch.name, type=ch.type.value if hasattr(ch.type, 'value') else str(ch.type),
            endpoint=ch.endpoint, api_key=ch.api_key, extra_keys=extra_keys, key_strategy=ch.key_strategy,
            priority=ch.priority, timeout=ch.timeout,
            status=ch.status.value if hasattr(ch.status, 'value') else str(ch.status),
            health_status=ch.health_status.value if hasattr(ch.health_status, "value") else (str(ch.health_status) if ch.health_status else None),
            last_check_at=ch.last_check_at, cooldown_until=ch.cooldown_until,
            quota_type=ch.quota_type, quota_hourly=ch.quota_hourly, quota_weekly=ch.quota_weekly,
            sync_enabled=ch.sync_enabled, sync_interval=ch.sync_interval, last_sync_at=ch.last_sync_at,
            quota_config=json.loads(ch.quota_config) if ch.quota_config else None,
            bound_models_count=bound_count
        ))
    
    return ChannelListResponse(total=total, items=items)


@router.post("/channels", response_model=ChannelResponse)
async def create_channel(data: ChannelCreate, request: Request, db: Session = Depends(get_db), admin: User = Depends(require_admin)):
    """创建渠道"""
    channel_id = data.name.lower().replace(" ", "_")[:20] + f"_{secrets.token_hex(4)}"
    
    channel = Channel(
        channel_id=channel_id, name=data.name, type=ChannelType(data.type),
        endpoint=data.endpoint, api_key=data.api_key,
        extra_keys=json.dumps(data.extra_keys) if data.extra_keys else None,
        key_strategy=data.key_strategy, priority=data.priority, timeout=data.timeout,
        quota_type=data.quota_type, quota_hourly=data.quota_hourly, quota_weekly=data.quota_weekly,
        sync_enabled=data.sync_enabled, sync_interval=data.sync_interval,
        quota_config=json.dumps(data.quota_config.dict()) if data.quota_config else None
    )
    db.add(channel)
    db.commit()
    db.refresh(channel)
    
    record_operation(db=db, operator=admin, action="create", target_type="channel", target_id=channel_id, detail={"name": data.name, "type": data.type}, ip_address=extract_client_ip(request))
    
    return ChannelResponse(
        channel_id=channel.channel_id, name=channel.name, type=channel.type.value,
        endpoint=channel.endpoint, api_key=channel.api_key,
        extra_keys=data.extra_keys, key_strategy=channel.key_strategy,
        priority=channel.priority, timeout=channel.timeout,
        status=channel.status.value, health_status=channel.health_status.value,
        quota_type=channel.quota_type, quota_hourly=channel.quota_hourly, quota_weekly=channel.quota_weekly,
        sync_enabled=channel.sync_enabled, sync_interval=channel.sync_interval
    )


@router.post("/channels/test-connection", response_model=ChannelTestResponse)
async def test_channel_connection(
    data: ChannelTestRequest,
    admin: User = Depends(require_admin)
):
    """测试渠道连接（无需入库，新建/编辑前都可调用）"""
    from app.services.channel_test_service import ChannelTestService
    service = ChannelTestService()
    return await service.test_connection(
        type_=data.type,
        endpoint=data.endpoint,
        api_key=data.api_key,
        timeout=data.timeout,
    )


# ========== 渠道配额 ==========

@router.get("/channels/quotas", response_model=ChannelQuotaListResponse)
async def list_channel_quotas(db: Session = Depends(get_db), admin: User = Depends(require_admin)):
    """所有渠道配额"""
    quotas = db.query(ChannelQuota).all()
    items = []
    for q in quotas:
        ch = db.query(Channel).filter(Channel.channel_id == q.channel_id).first()
        items.append(ChannelQuotaResponse(
            channel_id=q.channel_id, channel_name=ch.name if ch else None,
            hourly=QuotaDetail(limit=q.quota_limit, used=q.quota_used, remain=q.quota_remain, percent=float(q.quota_percent), last_sync=str(q.sync_at)) if q.quota_type == QuotaType.hourly else None,
            weekly=QuotaDetail(limit=q.quota_limit, used=q.quota_used, remain=q.quota_remain, percent=float(q.quota_percent), last_sync=str(q.sync_at)) if q.quota_type == QuotaType.weekly else None
        ))
    return ChannelQuotaListResponse(total=len(items), items=items)


@router.get("/channels/{channel_id}/quota")
async def get_channel_quota(channel_id: str, db: Session = Depends(get_db), admin: User = Depends(require_admin)):
    """单个渠道配额"""
    ch = db.query(Channel).filter(Channel.channel_id == channel_id).first()
    if not ch:
        raise HTTPException(status_code=404, detail="渠道不存在")
    
    quotas = db.query(ChannelQuota).filter(ChannelQuota.channel_id == channel_id).all()
    hourly = next((q for q in quotas if q.quota_type == QuotaType.hourly), None)
    weekly = next((q for q in quotas if q.quota_type == QuotaType.weekly), None)
    
    return ChannelQuotaResponse(
        channel_id=channel_id, channel_name=ch.name,
        hourly=QuotaDetail(limit=hourly.quota_limit, used=hourly.quota_used, remain=hourly.quota_remain, percent=float(hourly.quota_percent), last_sync=str(hourly.sync_at)) if hourly else None,
        weekly=QuotaDetail(limit=weekly.quota_limit, used=weekly.quota_used, remain=weekly.quota_remain, percent=float(weekly.quota_percent), last_sync=str(weekly.sync_at)) if weekly else None
    )


@router.post("/channels/{channel_id}/quota/sync")
async def sync_channel_quota(channel_id: str, request: Request, db: Session = Depends(get_db), admin: User = Depends(require_admin)):
    """手动同步渠道配额"""
    ch = db.query(Channel).filter(Channel.channel_id == channel_id).first()
    if not ch:
        raise HTTPException(status_code=404, detail="渠道不存在")
    
    from app.services.sync_service import create_sync_service
    sync_service = create_sync_service(db)
    await sync_service.sync_channel_quota(ch)
    
    record_operation(db=db, operator=admin, action="sync_quota", target_type="channel", target_id=channel_id, detail={}, ip_address=extract_client_ip(request))
    return {"message": "同步成功"}
@router.get("/channels/{channel_id}", response_model=ChannelWithModelsResponse)
async def get_channel(channel_id: str, db: Session = Depends(get_db), admin: User = Depends(require_admin)):
    """获取渠道详情（含绑定模型）"""
    channel = db.query(Channel).filter(Channel.channel_id == channel_id).first()
    if not channel:
        raise HTTPException(status_code=404, detail="渠道不存在")
    
    mc_list = db.query(ModelChannel).filter(ModelChannel.channel_id == channel_id).all()
    bound_models = []
    for mc in mc_list:
        model = db.query(Model).filter(Model.model_id == mc.model_id).first()
        bound_models.append(ModelChannelResponse(
            id=mc.id, model_id=mc.model_id, channel_id=mc.channel_id,
            upstream_model=mc.upstream_model, priority=mc.priority, weight=mc.weight,
            enabled=mc.enabled, created_at=mc.created_at,
            channel=ChannelResponse(
                channel_id=channel.channel_id, name=channel.name, type=channel.type.value,
                endpoint=channel.endpoint, api_key=channel.api_key,
                priority=channel.priority, timeout=channel.timeout,
                status=channel.status.value, health_status=channel.health_status.value
            ) if model else None
        ))
    
    extra_keys = json.loads(channel.extra_keys) if channel.extra_keys else None
    return ChannelWithModelsResponse(
        channel_id=channel.channel_id, name=channel.name, type=channel.type.value,
        endpoint=channel.endpoint, api_key=channel.api_key, extra_keys=extra_keys,
        key_strategy=channel.key_strategy, priority=channel.priority, timeout=channel.timeout,
        status=channel.status.value, health_status=channel.health_status.value,
        last_check_at=channel.last_check_at, cooldown_until=channel.cooldown_until,
        quota_type=channel.quota_type, quota_hourly=channel.quota_hourly, quota_weekly=channel.quota_weekly,
        sync_enabled=channel.sync_enabled, sync_interval=channel.sync_interval, last_sync_at=channel.last_sync_at,
        quota_config=json.loads(channel.quota_config) if channel.quota_config else None,
        bound_models_count=len(mc_list), bound_models=bound_models
    )


@router.put("/channels/{channel_id}")
async def update_channel(channel_id: str, data: ChannelUpdate, request: Request, db: Session = Depends(get_db), admin: User = Depends(require_admin)):
    """更新渠道"""
    channel = db.query(Channel).filter(Channel.channel_id == channel_id).first()
    if not channel:
        raise HTTPException(status_code=404, detail="渠道不存在")
    
    changed = {}
    for field, value in data.model_dump(exclude_unset=True).items():
        if value is None:
            continue
        if field == "extra_keys":
            value = json.dumps(value)
        if field == "quota_config":
            value = json.dumps(value.dict())
        if getattr(channel, field) != value:
            changed[field] = value
            setattr(channel, field, value)
    
    db.commit()
    record_operation(db=db, operator=admin, action="update", target_type="channel", target_id=channel_id, detail=changed, ip_address=extract_client_ip(request))
    return {"message": "更新成功"}


@router.delete("/channels/{channel_id}")
async def delete_channel(channel_id: str, request: Request, db: Session = Depends(get_db), admin: User = Depends(require_admin)):
    """删除渠道（级联删除 model_channels，保留 usage_logs）"""
    channel = db.query(Channel).filter(Channel.channel_id == channel_id).first()
    if not channel:
        raise HTTPException(status_code=404, detail="渠道不存在")
    
    # 删除 model_channels（级联）
    db.query(ModelChannel).filter(ModelChannel.channel_id == channel_id).delete()
    
    db.delete(channel)
    db.commit()
    
    record_operation(db=db, operator=admin, action="delete", target_type="channel", target_id=channel_id, detail={}, ip_address=extract_client_ip(request))
    return {"message": "删除成功"}


@router.get("/channels/{channel_id}/models")
async def get_channel_models(channel_id: str, db: Session = Depends(get_db), admin: User = Depends(require_admin)):
    """获取渠道绑定的模型列表"""
    channel = db.query(Channel).filter(Channel.channel_id == channel_id).first()
    if not channel:
        raise HTTPException(status_code=404, detail="渠道不存在")
    
    mc_list = db.query(ModelChannel).filter(ModelChannel.channel_id == channel_id).all()
    return {
        "channel_id": channel_id, "channel_name": channel.name,
        "total": len(mc_list),
        "items": [{"model_id": mc.model_id, "upstream_model": mc.upstream_model, "priority": mc.priority, "weight": mc.weight, "enabled": mc.enabled} for mc in mc_list]
    }


@router.post("/channels/{channel_id}/sync-models")
async def sync_channel_models(channel_id: str, request: Request, db: Session = Depends(get_db), admin: User = Depends(require_admin)):
    """一键从渠道拉取模型并自动创建/绑定"""
    channel = db.query(Channel).filter(Channel.channel_id == channel_id).first()
    if not channel:
        raise HTTPException(status_code=404, detail="渠道不存在")
    
    from app.services.model_sync_service import create_model_sync_service
    sync_service = create_model_sync_service(db)
    result = await sync_service.sync_channel_models(channel)
    
    record_operation(db=db, operator=admin, action="sync_models", target_type="channel", target_id=channel_id, detail={"count": result.get("count", 0)}, ip_address=extract_client_ip(request))
    return result


# ========== 模型管理 (Model) ==========

@router.get("/models", response_model=ModelListResponse)
async def list_models(
    page: int = Query(1, ge=1), page_size: int = Query(20, ge=1, le=100),
    keyword: Optional[str] = None, status: Optional[str] = None,
    db: Session = Depends(get_db), admin: User = Depends(require_admin)
):
    """模型列表"""
    query = db.query(Model)
    if keyword:
        query = query.filter(Model.model_id.contains(keyword) | Model.display_name.contains(keyword))
    if status:
        query = query.filter(Model.status == status)
    
    total = query.count()
    models = query.order_by(Model.created_at.desc()).offset((page - 1) * page_size).limit(page_size).all()
    
    items = []
    for m in models:
        bound_count = db.query(ModelChannel).filter(ModelChannel.model_id == m.model_id).count()
        items.append(ModelResponse(
            model_id=m.model_id, display_name=m.display_name, description=m.description,
            aliases=json.loads(m.aliases) if m.aliases else None,
            price_type=m.price_type.value if hasattr(m.price_type, 'value') else str(m.price_type),
            price_per_1k_input=float(m.price_per_1k_input) if m.price_per_1k_input else 0,
            price_per_1k_output=float(m.price_per_1k_output) if m.price_per_1k_output else 0,
            price_per_request=float(m.price_per_request) if m.price_per_request else 0,
            status=m.status.value if hasattr(m.status, 'value') else str(m.status),
            created_at=m.created_at, bound_channels_count=bound_count,
            model_groups=[]
        ))
    
    return ModelListResponse(total=total, items=items)


@router.post("/models", response_model=ModelResponse)
async def create_model(data: ModelCreate, request: Request, db: Session = Depends(get_db), admin: User = Depends(require_admin)):
    """创建模型（不绑定渠道）"""
    if not data.model_id:
        data.model_id = f"m_{secrets.token_hex(4)}"
    
    if db.query(Model).filter(Model.model_id == data.model_id).first():
        raise HTTPException(status_code=400, detail="模型ID已存在")
    
    model = Model(
        model_id=data.model_id, display_name=data.display_name or data.model_id,
        description=data.description, aliases=json.dumps(data.aliases) if data.aliases else None,
        price_type=PriceType(data.price_type),
        price_per_1k_input=data.price_per_1k_input, price_per_1k_output=data.price_per_1k_output,
        price_per_request=data.price_per_request, status=ModelStatus(data.status)
    )
    db.add(model)
    
    # 绑定到默认分组
    from app.models.model_group import bind_new_model_to_default_group
    bind_new_model_to_default_group(db, model)
    
    db.commit()
    db.refresh(model)
    
    record_operation(db=db, operator=admin, action="create", target_type="model", target_id=model.model_id, detail={"model_id": model.model_id}, ip_address=extract_client_ip(request))
    
    return ModelResponse(
        model_id=model.model_id, display_name=model.display_name, description=model.description,
        aliases=data.aliases, price_type=data.price_type,
        price_per_1k_input=data.price_per_1k_input, price_per_1k_output=data.price_per_1k_output,
        price_per_request=data.price_per_request, status=data.status, created_at=model.created_at,
        bound_channels_count=0, model_groups=[]
    )


@router.get("/models/{model_id}", response_model=ModelWithChannelsResponse)
async def get_model(model_id: str, db: Session = Depends(get_db), admin: User = Depends(require_admin)):
    """获取模型详情（含绑定渠道）"""
    model = db.query(Model).filter(Model.model_id == model_id).first()
    if not model:
        raise HTTPException(status_code=404, detail="模型不存在")
    
    mc_list = db.query(ModelChannel).filter(ModelChannel.model_id == model_id).all()
    bound_channels = []
    for mc in mc_list:
        ch = db.query(Channel).filter(Channel.channel_id == mc.channel_id).first()
        bound_channels.append(ModelChannelResponse(
            id=mc.id, model_id=mc.model_id, channel_id=mc.channel_id,
            upstream_model=mc.upstream_model, priority=mc.priority, weight=mc.weight,
            enabled=mc.enabled, created_at=mc.created_at,
            channel=ChannelResponse(
                channel_id=ch.channel_id, name=ch.name, type=ch.type.value,
                endpoint=ch.endpoint, api_key=ch.api_key, priority=ch.priority, timeout=ch.timeout,
                status=ch.status.value if ch.status else "active", health_status=ch.health_status.value if hasattr(ch.health_status, "value") else (str(ch.health_status) if ch.health_status else None)
            ) if ch else None
        ))
    
    return ModelWithChannelsResponse(
        model_id=model.model_id, display_name=model.display_name, description=model.description,
        aliases=json.loads(model.aliases) if model.aliases else None,
        price_type=model.price_type.value if hasattr(model.price_type, 'value') else str(model.price_type),
        price_per_1k_input=float(model.price_per_1k_input) if model.price_per_1k_input else 0,
        price_per_1k_output=float(model.price_per_1k_output) if model.price_per_1k_output else 0,
        price_per_request=float(model.price_per_request) if model.price_per_request else 0,
        status=model.status.value if hasattr(model.status, 'value') else str(model.status),
        created_at=model.created_at, bound_channels_count=len(mc_list),
        model_groups=[],
        bound_channels=bound_channels
    )


@router.put("/models/{model_id}")
async def update_model(model_id: str, data: ModelUpdate, request: Request, db: Session = Depends(get_db), admin: User = Depends(require_admin)):
    """更新模型"""
    model = db.query(Model).filter(Model.model_id == model_id).first()
    if not model:
        raise HTTPException(status_code=404, detail="模型不存在")
    
    changed = {}
    for field, value in data.model_dump(exclude_unset=True).items():
        if value is None:
            continue
        if field == "aliases":
            value = json.dumps(value)
        if getattr(model, field) != value:
            changed[field] = value
            setattr(model, field, value)
    
    db.commit()
    record_operation(db=db, operator=admin, action="update", target_type="model", target_id=model_id, detail=changed, ip_address=extract_client_ip(request))
    return {"message": "更新成功"}


@router.delete("/models/{model_id}")
async def delete_model(model_id: str, request: Request, db: Session = Depends(get_db), admin: User = Depends(require_admin)):
    """删除模型（级联删除 model_channels，保留 usage_logs）"""
    model = db.query(Model).filter(Model.model_id == model_id).first()
    if not model:
        raise HTTPException(status_code=404, detail="模型不存在")
    
    db.query(ModelChannel).filter(ModelChannel.model_id == model_id).delete()
    db.delete(model)
    db.commit()
    
    record_operation(db=db, operator=admin, action="delete", target_type="model", target_id=model_id, detail={}, ip_address=extract_client_ip(request))
    return {"message": "删除成功"}


# ========== 模型-渠道绑定管理 ==========

@router.get("/models/{model_id}/channels", response_model=List[ModelChannelResponse])
async def list_model_channels(model_id: str, db: Session = Depends(get_db), admin: User = Depends(require_admin)):
    """获取模型已绑定的渠道列表"""
    model = db.query(Model).filter(Model.model_id == model_id).first()
    if not model:
        raise HTTPException(status_code=404, detail="模型不存在")

    rows = db.query(ModelChannel).filter(ModelChannel.model_id == model_id).all()
    channel_ids = {r.channel_id for r in rows}
    channels_map = {
        ch.channel_id: ch
        for ch in db.query(Channel).filter(Channel.channel_id.in_(channel_ids)).all()
    } if channel_ids else {}

    items = []
    for mc in rows:
        ch = channels_map.get(mc.channel_id)
        items.append(ModelChannelResponse(
            id=mc.id, model_id=mc.model_id, channel_id=mc.channel_id,
            upstream_model=mc.upstream_model, priority=mc.priority,
            weight=mc.weight, enabled=mc.enabled, created_at=mc.created_at,
            channel=ChannelResponse(
                channel_id=ch.channel_id, name=ch.name, type=ch.type.value,
                endpoint=ch.endpoint, api_key=ch.api_key,
                priority=ch.priority, timeout=ch.timeout,
                status=ch.status.value, health_status=ch.health_status.value if hasattr(ch.health_status, "value") else (str(ch.health_status) if ch.health_status else None)
            ) if ch else None,
        ))
    return items


@router.put("/models/{model_id}/channels")
async def replace_model_channels(model_id: str, data: List[ModelChannelCreate], request: Request, db: Session = Depends(get_db), admin: User = Depends(require_admin)):
    """整体替换模型-渠道绑定"""
    model = db.query(Model).filter(Model.model_id == model_id).first()
    if not model:
        raise HTTPException(status_code=404, detail="模型不存在")
    
    # 删除旧的
    db.query(ModelChannel).filter(ModelChannel.model_id == model_id).delete()
    
    # 添加新的
    for mc_data in data:
        mc = ModelChannel(
            model_id=model_id, channel_id=mc_data.channel_id,
            upstream_model=mc_data.upstream_model, priority=mc_data.priority,
            weight=mc_data.weight, enabled=mc_data.enabled
        )
        db.add(mc)
    
    db.commit()
    record_operation(db=db, operator=admin, action="replace_channels", target_type="model", target_id=model_id, detail={"count": len(data)}, ip_address=extract_client_ip(request))
    return {"message": "更新成功", "count": len(data)}


@router.post("/models/{model_id}/channels")
async def add_model_channel(model_id: str, data: ModelChannelCreate, request: Request, db: Session = Depends(get_db), admin: User = Depends(require_admin)):
    """增量添加模型-渠道绑定"""
    model = db.query(Model).filter(Model.model_id == model_id).first()
    if not model:
        raise HTTPException(status_code=404, detail="模型不存在")
    
    existing = db.query(ModelChannel).filter(
        ModelChannel.model_id == model_id,
        ModelChannel.channel_id == data.channel_id
    ).first()
    if existing:
        raise HTTPException(status_code=400, detail="该渠道已绑定到此模型")
    
    mc = ModelChannel(
        model_id=model_id, channel_id=data.channel_id,
        upstream_model=data.upstream_model, priority=data.priority,
        weight=data.weight, enabled=data.enabled
    )
    db.add(mc)
    db.commit()
    db.refresh(mc)
    
    record_operation(db=db, operator=admin, action="bind_channel", target_type="model", target_id=model_id, detail={"channel_id": data.channel_id}, ip_address=extract_client_ip(request))
    return {"message": "绑定成功", "id": mc.id}


@router.delete("/models/{model_id}/channels/{channel_id}")
async def remove_model_channel(model_id: str, channel_id: str, request: Request, db: Session = Depends(get_db), admin: User = Depends(require_admin)):
    """解绑模型-渠道"""
    mc = db.query(ModelChannel).filter(
        ModelChannel.model_id == model_id,
        ModelChannel.channel_id == channel_id
    ).first()
    if not mc:
        raise HTTPException(status_code=404, detail="绑定不存在")
    
    db.delete(mc)
    db.commit()
    
    record_operation(db=db, operator=admin, action="unbind_channel", target_type="model", target_id=model_id, detail={"channel_id": channel_id}, ip_address=extract_client_ip(request))
    return {"message": "解绑成功"}


@router.patch("/models/{model_id}/channels/{channel_id}")
async def update_model_channel(model_id: str, channel_id: str, data: ModelChannelUpdate, request: Request, db: Session = Depends(get_db), admin: User = Depends(require_admin)):
    """修改模型-渠道绑定参数"""
    mc = db.query(ModelChannel).filter(
        ModelChannel.model_id == model_id,
        ModelChannel.channel_id == channel_id
    ).first()
    if not mc:
        raise HTTPException(status_code=404, detail="绑定不存在")
    
    changed = {}
    for field, value in data.model_dump(exclude_unset=True).items():
        if value is not None and getattr(mc, field) != value:
            changed[field] = value
            setattr(mc, field, value)
    
    db.commit()
    record_operation(db=db, operator=admin, action="update_channel_binding", target_type="model", target_id=model_id, detail=changed, ip_address=extract_client_ip(request))
    return {"message": "更新成功"}




# ========== 兼容性路由 (GC-7) ==========

@router.get("/providers", include_in_schema=False)
async def providers_redirect():
    """兼容旧路由"""
    return RedirectResponse(url="/api/v1/admin/channels", status_code=308)

@router.post("/providers", include_in_schema=False)
async def providers_post_redirect():
    return RedirectResponse(url="/api/v1/admin/channels", status_code=308)

@router.get("/providers/{path:path}", include_in_schema=False)
async def providers_sub_redirect(path: str):
    return RedirectResponse(url=f"/api/v1/admin/channels/{path}", status_code=308)
