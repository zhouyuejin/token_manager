"""
管理后台接口
"""
import secrets
from typing import Optional
from datetime import datetime
from sqlalchemy import func, and_

from fastapi import APIRouter, Depends, HTTPException, status, Query, Request
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.core.security import get_password_hash
from app.models.user import User, UserRole, UserStatus
from app.models.provider import Provider, ProviderType, ProviderStatus
from app.models.provider_quota import ProviderQuota, QuotaType
from app.models.model_mapping import ModelMapping, ModelMappingStatus
from app.dependencies import get_current_user, require_admin
from app.schemas.admin import (
    AdminUserCreate, AdminUserUpdate, AdminUserResponse,
    UserListResponse, QuotaAdjustRequest,
    ProviderCreate, ProviderUpdate, ProviderResponse, ProviderListResponse,
    ModelMappingCreate, ModelMappingUpdate, ModelMappingResponse, ModelMappingListResponse
)
from app.services.operation_log_service import record_operation
from app.services.sync_service import create_sync_service
from app.utils.request import extract_client_ip

router = APIRouter()

# ========== 用户管理 ==========

@router.get("/users", response_model=UserListResponse)
async def list_users(
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    keyword: Optional[str] = None,
    role: Optional[str] = None,
    status: Optional[str] = None,
    db: Session = Depends(get_db),
    admin: User = Depends(require_admin)
):
    """
    用户列表（管理员）
    """
    query = db.query(User)
    
    if keyword:
        query = query.filter(
            (User.username.like(f"%{keyword}%")) | 
            (User.email.like(f"%{keyword}%"))
        )
    if role:
        query = query.filter(User.role == UserRole(role))
    if status:
        query = query.filter(User.status == UserStatus(status))
    
    total = query.count()
    items = query.offset((page - 1) * page_size).limit(page_size).all()
    
    return UserListResponse(
        total=total,
        items=[
            AdminUserResponse(
                user_id=u.user_id,
                username=u.username,
                email=u.email,
                role=u.role.value,
                status=u.status.value,
                quota=u.quota,
                quota_used=u.quota_used,
                created_at=u.created_at
            )
            for u in items
        ]
    )


@router.post("/users", response_model=AdminUserResponse)
async def create_user(
    request: Request,
    user_data: AdminUserCreate,
    db: Session = Depends(get_db),
    admin: User = Depends(require_admin)
):
    """
    创建用户（管理员）
    """
    # 检查用户名
    if db.query(User).filter(User.username == user_data.username).first():
        raise HTTPException(status_code=400, detail="用户名已存在")
    
    # 检查邮箱
    if db.query(User).filter(User.email == user_data.email).first():
        raise HTTPException(status_code=400, detail="邮箱已被注册")
    
    # 创建用户
    user = User(
        user_id=f"usr_{secrets.token_hex(8)}",
        username=user_data.username,
        email=user_data.email,
        password=get_password_hash(user_data.password),
        role=UserRole(user_data.role) if user_data.role else UserRole.user,
        quota=user_data.quota,
        status=UserStatus.active
    )
    
    db.add(user)
    db.commit()
    db.refresh(user)
    
    ip_address = extract_client_ip(request)
    record_operation(
        db=db,
        operator=admin,
        action="create",
        target_type="user",
        target_id=user.user_id,
        detail={
            "username": user.username,
            "email": user.email,
            "role": user.role.value,
            "quota": user.quota,
        },
        ip_address=ip_address,
    )
    
    return AdminUserResponse(
        user_id=user.user_id,
        username=user.username,
        email=user.email,
        role=user.role.value,
        status=user.status.value,
        quota=user.quota,
        quota_used=user.quota_used,
        created_at=user.created_at
    )


@router.put("/users/{user_id}")
async def update_user(
    request: Request,
    user_id: str,
    user_data: AdminUserUpdate,
    db: Session = Depends(get_db),
    admin: User = Depends(require_admin)
):
    """
    更新用户（管理员）
    """
    user = db.query(User).filter(User.user_id == user_id).first()
    if not user:
        raise HTTPException(status_code=404, detail="用户不存在")
    
    # 不能编辑管理员用户
    if user.role == UserRole.admin:
        raise HTTPException(status_code=400, detail="不能编辑管理员用户")
    
    changed = {}
    if user_data.role is not None:
        changed["role"] = user_data.role
        user.role = UserRole(user_data.role)
    if user_data.status is not None:
        changed["status"] = user_data.status
        user.status = UserStatus(user_data.status)
    if user_data.quota is not None:
        changed["quota"] = user_data.quota
        user.quota = user_data.quota
    
    db.commit()
    
    ip_address = extract_client_ip(request)
    record_operation(
        db=db,
        operator=admin,
        action="update",
        target_type="user",
        target_id=user_id,
        detail=changed,
        ip_address=ip_address,
    )
    
    return {"message": "更新成功"}


@router.delete("/users/{user_id}")
async def delete_user(
    request: Request,
    user_id: str,
    db: Session = Depends(get_db),
    admin: User = Depends(require_admin)
):
    """
    删除用户（管理员）
    """
    user = db.query(User).filter(User.user_id == user_id).first()
    if not user:
        raise HTTPException(status_code=404, detail="用户不存在")
    
    # 不能删除管理员用户
    if user.role == UserRole.admin:
        raise HTTPException(status_code=400, detail="不能删除管理员用户")
    
    # 不能删除自己
    if user.user_id == admin.user_id:
        raise HTTPException(status_code=400, detail="不能删除自己的账户")
    
    deleted_username = user.username
    
    db.delete(user)
    db.commit()
    
    ip_address = extract_client_ip(request)
    record_operation(
        db=db,
        operator=admin,
        action="delete",
        target_type="user",
        target_id=user_id,
        detail={"username": deleted_username},
        ip_address=ip_address,
    )
    
    return {"message": "删除成功"}


@router.post("/users/{user_id}/quota")
async def adjust_user_quota(
    request: Request,
    user_id: str,
    quota_data: QuotaAdjustRequest,
    db: Session = Depends(get_db),
    admin: User = Depends(require_admin)
):
    """
    调整用户额度（管理员）
    """
    user = db.query(User).filter(User.user_id == user_id).first()
    if not user:
        raise HTTPException(status_code=404, detail="用户不存在")
    
    before = user.quota
    # 调整额度
    user.quota += quota_data.amount
    if user.quota < 0:
        user.quota = 0
    after = user.quota
    
    db.commit()
    
    ip_address = extract_client_ip(request)
    record_operation(
        db=db,
        operator=admin,
        action="quota_adjust",
        target_type="user",
        target_id=user_id,
        detail={
            "amount": quota_data.amount,
            "reason": quota_data.reason,
            "before": before,
            "after": after,
        },
        ip_address=ip_address,
    )
    
    return {
        "message": "额度调整成功",
        "new_quota": user.quota
    }


# ========== 供应商管理 ==========

@router.get("/providers", response_model=ProviderListResponse)
async def list_providers(
    db: Session = Depends(get_db),
    admin: User = Depends(require_admin)
):
    """
    供应商列表（管理员）
    """
    providers = db.query(Provider).all()
    
    return ProviderListResponse(
        total=len(providers),
        items=[
            ProviderResponse(
                provider_id=p.provider_id,
                name=p.name,
                type=p.type.value,
                endpoint=p.endpoint,
                priority=p.priority,
                timeout=p.timeout,
                status=p.status.value,
                health_status=p.health_status.value if p.health_status else "healthy",
                last_check_at=p.last_check_at,
                quota_hourly=p.quota_hourly,
                quota_weekly=p.quota_weekly,
                sync_enabled=bool(p.sync_enabled) if p.sync_enabled else False,
                sync_interval=p.sync_interval or 300,
                last_sync_at=p.last_sync_at,
                quota_config=json.loads(p.quota_config) if p.quota_config else None
            )
            for p in providers
        ]
    )


@router.post("/providers", response_model=ProviderResponse)
async def create_provider(
    request: Request,
    provider_data: ProviderCreate,
    db: Session = Depends(get_db),
    admin: User = Depends(require_admin)
):
    """
    创建供应商（管理员）
    """
    provider = Provider(
        provider_id=f"prov_{secrets.token_hex(8)}",
        name=provider_data.name,
        type=ProviderType(provider_data.type),
        endpoint=provider_data.endpoint,
        api_key=provider_data.api_key,
        priority=provider_data.priority,
        timeout=provider_data.timeout,
        quota_hourly=provider_data.quota_hourly,
        quota_weekly=provider_data.quota_weekly,
        quota_config=json.dumps(provider_data.quota_config.model_dump()) if provider_data.quota_config else None,
        status=ProviderStatus.active
    )
    
    db.add(provider)
    db.commit()
    db.refresh(provider)
    
    # 更新同步任务
    try:
        from app.services.scheduler_service import update_provider_sync_job
        interval_seconds = provider_data.sync_interval or 300
        if provider_data.sync_enabled:
            update_provider_sync_job(
                provider.provider_id,
                provider.name,
                provider_data.sync_enabled,
                interval_seconds
            )
    except Exception as e:
        logger.warning(f"更新同步任务失败: {e}")
    
    ip_address = extract_client_ip(request)
    record_operation(
        db=db,
        operator=admin,
        action="create",
        target_type="provider",
        target_id=provider.provider_id,
        detail={
            "name": provider.name,
            "type": provider.type.value,
            "endpoint": provider.endpoint,
            "priority": provider.priority,
            "timeout": provider.timeout,
            "quota_hourly": provider.quota_hourly,
            "quota_weekly": provider.quota_weekly,
        },
        ip_address=ip_address,
    )
    
    return ProviderResponse(
        provider_id=provider.provider_id,
        name=provider.name,
        type=provider.type.value,
        endpoint=provider.endpoint,
        priority=provider.priority,
        timeout=provider.timeout,
        status=provider.status.value,
        health_status=provider.health_status.value if provider.health_status else "healthy",
        last_check_at=provider.last_check_at,
        quota_hourly=provider.quota_hourly,
        quota_weekly=provider.quota_weekly,
        sync_enabled=bool(provider.sync_enabled) if provider.sync_enabled else False,
        sync_interval=provider.sync_interval or 300,
        last_sync_at=provider.last_sync_at,
        quota_config=json.loads(provider.quota_config) if provider.quota_config else None
    )


@router.put("/providers/{provider_id}")
async def update_provider(
    request: Request,
    provider_id: str,
    provider_data: ProviderUpdate,
    db: Session = Depends(get_db),
    admin: User = Depends(require_admin)
):
    """
    更新供应商（管理员）
    """
    provider = db.query(Provider).filter(Provider.provider_id == provider_id).first()
    if not provider:
        raise HTTPException(status_code=404, detail="供应商不存在")
    
    changed = {}
    if provider_data.name is not None:
        changed["name"] = provider_data.name
        provider.name = provider_data.name
    if provider_data.type is not None:
        changed["type"] = provider_data.type
        provider.type = ProviderType(provider_data.type)
    if provider_data.endpoint is not None:
        changed["endpoint"] = provider_data.endpoint
        provider.endpoint = provider_data.endpoint
    if provider_data.api_key is not None and provider_data.api_key:
        changed["api_key_rotated"] = True
        provider.api_key = provider_data.api_key
    if provider_data.priority is not None:
        changed["priority"] = provider_data.priority
        provider.priority = provider_data.priority
    if provider_data.timeout is not None:
        changed["timeout"] = provider_data.timeout
        provider.timeout = provider_data.timeout
    if provider_data.status is not None:
        changed["status"] = provider_data.status
        provider.status = ProviderStatus(provider_data.status)
    if provider_data.quota_hourly is not None:
        changed["quota_hourly"] = provider_data.quota_hourly
        provider.quota_hourly = provider_data.quota_hourly
    if provider_data.quota_weekly is not None:
        changed["quota_weekly"] = provider_data.quota_weekly
        provider.quota_weekly = provider_data.quota_weekly
    if provider_data.sync_enabled is not None:
        changed["sync_enabled"] = provider_data.sync_enabled
        provider.sync_enabled = 1 if provider_data.sync_enabled else 0
    if provider_data.sync_interval is not None:
        changed["sync_interval"] = provider_data.sync_interval
        provider.sync_interval = provider_data.sync_interval
    if provider_data.quota_config is not None:
        changed["quota_config"] = provider_data.quota_config.model_dump()
        provider.quota_config = json.dumps(provider_data.quota_config.model_dump())
    
    db.commit()
    
    # 更新同步任务
    try:
        from app.services.scheduler_service import update_provider_sync_job
        if provider_data.sync_enabled is not None or provider_data.sync_interval is not None:
            sync_enabled = provider_data.sync_enabled if provider_data.sync_enabled is not None else (provider.sync_enabled == 1)
            sync_interval = provider_data.sync_interval if provider_data.sync_interval is not None else (provider.sync_interval or 300)
            update_provider_sync_job(
                provider.provider_id,
                provider.name,
                sync_enabled,
                sync_interval
            )
    except Exception as e:
        logger.warning(f"更新同步任务失败: {e}")
    
    ip_address = extract_client_ip(request)
    record_operation(
        db=db,
        operator=admin,
        action="update",
        target_type="provider",
        target_id=provider_id,
        detail=changed,
        ip_address=ip_address,
    )
    
    return {"message": "更新成功"}


@router.delete("/providers/{provider_id}")
async def delete_provider(
    request: Request,
    provider_id: str,
    db: Session = Depends(get_db),
    admin: User = Depends(require_admin)
):
    """
    删除供应商（管理员）
    """
    provider = db.query(Provider).filter(Provider.provider_id == provider_id).first()
    if not provider:
        raise HTTPException(status_code=404, detail="供应商不存在")
    
    db.delete(provider)
    db.commit()
    
    ip_address = extract_client_ip(request)
    record_operation(
        db=db,
        operator=admin,
        action="delete",
        target_type="provider",
        target_id=provider_id,
        ip_address=ip_address,
    )
    
    return {"message": "删除成功"}

@router.get("/providers/quotas")
async def get_all_provider_quotas(
    db: Session = Depends(get_db),
    admin: User = Depends(require_admin)
):
    """
    获取所有供应商配额
    """
    providers = db.query(Provider).all()
    
    result = []
    for p in providers:
        # 从 provider_quotas 表获取实际用量
        hourly_quota = db.query(ProviderQuota).filter(
            ProviderQuota.provider_id == p.provider_id,
            ProviderQuota.quota_type == QuotaType.hourly
        ).first()
        
        weekly_quota = db.query(ProviderQuota).filter(
            ProviderQuota.provider_id == p.provider_id,
            ProviderQuota.quota_type == QuotaType.weekly
        ).first()
        
        hourly_limit = hourly_quota.quota_limit if hourly_quota else p.quota_hourly
        hourly_used = hourly_quota.quota_used if hourly_quota else 0
        hourly_remain = hourly_quota.quota_remain if hourly_quota else p.quota_hourly
        hourly_percent = float(hourly_quota.quota_percent) if hourly_quota and hourly_quota.quota_percent else 0
        hourly_sync = hourly_quota.sync_at.isoformat() + "Z" if hourly_quota and hourly_quota.sync_at else None
        import json
        hourly_raw = json.loads(hourly_quota.raw_data) if hourly_quota and hourly_quota.raw_data else None
        
        weekly_limit = weekly_quota.quota_limit if weekly_quota else p.quota_weekly
        weekly_used = weekly_quota.quota_used if weekly_quota else 0
        weekly_remain = weekly_quota.quota_remain if weekly_quota else p.quota_weekly
        weekly_percent = float(weekly_quota.quota_percent) if weekly_quota and weekly_quota.quota_percent else 0
        weekly_sync = weekly_quota.sync_at.isoformat() + "Z" if weekly_quota and weekly_quota.sync_at else None
        weekly_raw = json.loads(weekly_quota.raw_data) if weekly_quota and weekly_quota.raw_data else None
        
        result.append({
            "provider_id": p.provider_id,
            "provider_name": p.name,
            "hourly": {
                "limit": hourly_limit,
                "used": hourly_used,
                "remain": hourly_remain,
                "percent": hourly_percent,
                "reset_at": None,
                "last_sync": hourly_sync,
                "raw_data": hourly_raw
            },
            "weekly": {
                "limit": weekly_limit,
                "used": weekly_used,
                "remain": weekly_remain,
                "percent": weekly_percent,
                "reset_at": None,
                "last_sync": weekly_sync,
                "raw_data": weekly_raw
            }
        })
    
    return {"items": result}

@router.post("/providers/{provider_id}/quota/sync")
async def sync_provider_quota(
    request: Request,
    provider_id: str,
    db: Session = Depends(get_db),
    admin: User = Depends(require_admin)
):
    """
    手动同步供应商配额
    """
    provider = db.query(Provider).filter(Provider.provider_id == provider_id).first()
    if not provider:
        raise HTTPException(status_code=404, detail="供应商不存在")
    
    # 创建同步服务并执行同步
    sync_service = create_sync_service(db)
    success = await sync_service.sync_provider_quota(provider)
    
    if not success:
        raise HTTPException(status_code=500, detail="同步失败")
    
    ip_address = extract_client_ip(request)
    record_operation(
        db=db,
        operator=admin,
        action="sync",
        target_type="provider_quota",
        target_id=provider_id,
        ip_address=ip_address,
    )
    
    return {"message": "同步成功", "provider_id": provider_id}


@router.put("/providers/{provider_id}/quota")
async def update_provider_quota(
    request: Request,
    provider_id: str,
    quota_data: dict,
    db: Session = Depends(get_db),
    admin: User = Depends(require_admin)
):
    """
    更新供应商用量配置（额度、同步设置、自定义查询配置）
    """
    provider = db.query(Provider).filter(Provider.provider_id == provider_id).first()
    if not provider:
        raise HTTPException(status_code=404, detail="供应商不存在")
    
    changed = {}
    
    # 更新额度
    if "quota_hourly" in quota_data and quota_data["quota_hourly"] is not None:
        changed["quota_hourly"] = quota_data["quota_hourly"]
        provider.quota_hourly = quota_data["quota_hourly"]
    
    if "quota_weekly" in quota_data and quota_data["quota_weekly"] is not None:
        changed["quota_weekly"] = quota_data["quota_weekly"]
        provider.quota_weekly = quota_data["quota_weekly"]
    
    # 更新同步设置
    if "sync_enabled" in quota_data and quota_data["sync_enabled"] is not None:
        changed["sync_enabled"] = quota_data["sync_enabled"]
        provider.sync_enabled = 1 if quota_data["sync_enabled"] else 0
    
    if "sync_interval" in quota_data and quota_data["sync_interval"] is not None:
        changed["sync_interval"] = quota_data["sync_interval"]
        provider.sync_interval = quota_data["sync_interval"]
    
    # 更新自定义查询配置
    if "quota_config" in quota_data and quota_data["quota_config"] is not None:
        changed["quota_config"] = quota_data["quota_config"]
        provider.quota_config = json.dumps(quota_data["quota_config"])
    
    db.commit()
    
    # 更新同步任务
    try:
        from app.services.scheduler_service import update_provider_sync_job
        sync_enabled = quota_data.get("sync_enabled", provider.sync_enabled == 1)
        sync_interval = quota_data.get("sync_interval", provider.sync_interval or 300)
        logger.info(f"[API] 更新供应商 {provider.name} 同步配置: enabled={sync_enabled}, interval={sync_interval}")
        update_provider_sync_job(
            provider.provider_id,
            provider.name,
            sync_enabled,
            sync_interval
        )
    except Exception as e:
        logger.warning(f"更新同步任务失败: {e}")
    
    ip_address = extract_client_ip(request)
    record_operation(
        db=db,
        operator=admin,
        action="update_quota",
        target_type="provider_quota",
        target_id=provider_id,
        detail=changed,
        ip_address=ip_address,
    )
    
    return {
        "message": "用量配置更新成功",
        "provider_id": provider_id,
        "quota_hourly": provider.quota_hourly,
        "quota_weekly": provider.quota_weekly,
        "sync_enabled": provider.sync_enabled == 1,
        "sync_interval": provider.sync_interval,
        "quota_config": json.loads(provider.quota_config) if provider.quota_config else None
    }


# ========== 模型映射管理 ==========

@router.get("/models", response_model=ModelMappingListResponse)
async def list_models(
    db: Session = Depends(get_db),
    admin: User = Depends(require_admin)
):
    """
    模型映射列表（管理员）
    """
    models = db.query(ModelMapping).all()
    
    return ModelMappingListResponse(
        total=len(models),
        items=[
            ModelMappingResponse(
                model_id=m.model_id,
                display_name=m.display_name,
                provider_id=m.provider_id,
                provider_model=m.provider_model,
                aliases=m.aliases,
                status=m.status.value
            )
            for m in models
        ]
    )


@router.post("/models", response_model=ModelMappingResponse)
async def create_model_mapping(
    request: Request,
    model_data: ModelMappingCreate,
    db: Session = Depends(get_db),
    admin: User = Depends(require_admin)
):
    """
    创建模型映射（管理员）
    """
    # 如果没有传model_id，则自动生成一个
    if not model_data.model_id:
        model_id = f"model_{secrets.token_hex(8)}"
    else:
        model_id = model_data.model_id
    
    # 检查model_id是否已存在
    existing = db.query(ModelMapping).filter(
        ModelMapping.model_id == model_id
    ).first()
    if existing:
        raise HTTPException(status_code=400, detail="模型ID已存在")
    
    mapping = ModelMapping(
        model_id=model_id,
        display_name=model_data.display_name,
        provider_id=model_data.provider_id,
        provider_model=model_data.provider_model,
        aliases=model_data.aliases,
        status=ModelMappingStatus(model_data.status) if model_data.status else ModelMappingStatus.active
    )
    
    db.add(mapping)
    db.commit()
    db.refresh(mapping)
    
    ip_address = extract_client_ip(request)
    record_operation(
        db=db,
        operator=admin,
        action="create",
        target_type="model_mapping",
        target_id=mapping.model_id,
        detail={
            "display_name": mapping.display_name,
            "provider_id": mapping.provider_id,
            "provider_model": mapping.provider_model,
            "aliases": mapping.aliases,
        },
        ip_address=ip_address,
    )
    
    return ModelMappingResponse(
        model_id=mapping.model_id,
        display_name=mapping.display_name,
        provider_id=mapping.provider_id,
        provider_model=mapping.provider_model,
        aliases=mapping.aliases,
        status=mapping.status.value,
        created_at=mapping.created_at
    )


@router.put("/models/{model_id}")
async def update_model_mapping(
    request: Request,
    model_id: str,
    model_data: ModelMappingUpdate,
    db: Session = Depends(get_db),
    admin: User = Depends(require_admin)
):
    """
    更新模型映射（管理员）
    """
    mapping = db.query(ModelMapping).filter(
        ModelMapping.model_id == model_id
    ).first()
    if not mapping:
        raise HTTPException(status_code=404, detail="模型映射不存在")
    
    changed = {}
    if model_data.display_name is not None:
        changed["display_name"] = model_data.display_name
        mapping.display_name = model_data.display_name
    if model_data.provider_id is not None:
        changed["provider_id"] = model_data.provider_id
        mapping.provider_id = model_data.provider_id
    if model_data.provider_model is not None:
        changed["provider_model"] = model_data.provider_model
        mapping.provider_model = model_data.provider_model
    if model_data.aliases is not None:
        changed["aliases"] = model_data.aliases
        mapping.aliases = model_data.aliases
    if model_data.status is not None:
        changed["status"] = model_data.status
        mapping.status = ModelMappingStatus(model_data.status)
    
    db.commit()
    
    ip_address = extract_client_ip(request)
    record_operation(
        db=db,
        operator=admin,
        action="update",
        target_type="model_mapping",
        target_id=model_id,
        detail=changed,
        ip_address=ip_address,
    )
    
    return {"message": "更新成功"}


@router.delete("/models/{model_id}")
async def delete_model_mapping(
    request: Request,
    model_id: str,
    db: Session = Depends(get_db),
    admin: User = Depends(require_admin)
):
    """
    删除模型映射（管理员）
    """
    mapping = db.query(ModelMapping).filter(
        ModelMapping.model_id == model_id
    ).first()
    if not mapping:
        raise HTTPException(status_code=404, detail="模型映射不存在")
    
    db.delete(mapping)
    db.commit()
    
    ip_address = extract_client_ip(request)
    record_operation(
        db=db,
        operator=admin,
        action="delete",
        target_type="model_mapping",
        target_id=model_id,
        ip_address=ip_address,
    )
    
    return {"message": "删除成功"}


# ========== 模型同步管理 ==========

@router.get("/providers/{provider_id}/models")
async def get_provider_models(
    provider_id: str,
    db: Session = Depends(get_db),
    admin: User = Depends(require_admin)
):
    """
    获取供应商已同步的模型列表
    """
    provider = db.query(Provider).filter(
        Provider.provider_id == provider_id
    ).first()
    
    if not provider:
        raise HTTPException(status_code=404, detail="供应商不存在")
    
    from app.services.model_sync_service import create_model_sync_service
    sync_service = create_model_sync_service(db)
    models = sync_service.get_provider_models(provider)
    
    return {
        "provider_id": provider.provider_id,
        "provider_name": provider.name,
        "models": [m.to_dict() for m in models],
        "last_sync_at": provider.last_models_sync_at.isoformat() if provider.last_models_sync_at else None
    }


@router.post("/providers/{provider_id}/models/sync")
async def sync_provider_models(
    request: Request,
    provider_id: str,
    db: Session = Depends(get_db),
    admin: User = Depends(require_admin)
):
    """
    同步单个供应商的模型列表
    """
    provider = db.query(Provider).filter(
        Provider.provider_id == provider_id
    ).first()
    
    if not provider:
        raise HTTPException(status_code=404, detail="供应商不存在")
    
    from app.services.model_sync_service import create_model_sync_service
    sync_service = create_model_sync_service(db)
    
    result = await sync_service.sync_provider_models(provider)
    
    # 记录操作
    ip_address = extract_client_ip(request)
    record_operation(
        db=db,
        operator=admin,
        action="sync_models",
        target_type="provider",
        target_id=provider_id,
        detail={"model_count": result.get("count", 0)},
        ip_address=ip_address,
    )
    
    return result


@router.post("/providers/models/sync-all")
async def sync_all_provider_models(
    request: Request,
    db: Session = Depends(get_db),
    admin: User = Depends(require_admin)
):
    """
    同步所有供应商的模型列表
    """
    from app.services.model_sync_service import create_model_sync_service
    sync_service = create_model_sync_service(db)
    
    result = await sync_service.sync_all_providers()
    
    # 记录操作
    ip_address = extract_client_ip(request)
    record_operation(
        db=db,
        operator=admin,
        action="sync_all_models",
        target_type="provider",
        target_id="all",
        detail={"success": result["success"], "failed": result["failed"]},
        ip_address=ip_address,
    )
    
    return result


# ========== 模型映射自动创建 ==========

@router.post("/providers/{provider_id}/models/auto-create-mappings")
async def auto_create_model_mappings(
    request: Request,
    provider_id: str,
    db: Session = Depends(get_db),
    admin: User = Depends(require_admin)
):
    """
    自动创建模型映射
    """
    provider = db.query(Provider).filter(
        Provider.provider_id == provider_id
    ).first()
    
    if not provider:
        raise HTTPException(status_code=404, detail="供应商不存在")
    
    from app.services.model_sync_service import sync_and_create_mappings
    
    result = await sync_and_create_mappings(db, provider, auto_enable=True)
    
    # 记录操作
    ip_address = extract_client_ip(request)
    record_operation(
        db=db,
        operator=admin,
        action="auto_create_mappings",
        target_type="provider",
        target_id=provider_id,
        detail={"created": result.get("mapping_created", 0), "skipped": result.get("mapping_skipped", 0)},
        ip_address=ip_address,
    )
    
    return result


@router.post("/providers/models/sync-all-with-mappings")
async def sync_all_with_mappings(
    request: Request,
    db: Session = Depends(get_db),
    admin: User = Depends(require_admin)
):
    """
    同步所有供应商模型并自动创建映射
    """
    from app.services.model_sync_service import sync_and_create_mappings
    
    providers = db.query(Provider).filter(
        Provider.status == "active"
    ).all()
    
    results = []
    total_models = 0
    total_mappings = 0
    
    for provider in providers:
        result = await sync_and_create_mappings(db, provider, auto_enable=True)
        results.append({
            "provider_id": provider.provider_id,
            "provider_name": provider.name,
            **result
        })
        if result.get("sync_success"):
            total_models += result.get("sync_count", 0)
            total_mappings += result.get("mapping_created", 0)
    
    # 记录操作
    ip_address = extract_client_ip(request)
    record_operation(
        db=db,
        operator=admin,
        action="sync_all_with_mappings",
        target_type="provider",
        target_id="all",
        detail={"total_models": total_models, "total_mappings": total_mappings},
        ip_address=ip_address,
    )
    
    return {
        "total_providers": len(providers),
        "total_models": total_models,
        "total_mappings": total_mappings,
        "results": results
    }
