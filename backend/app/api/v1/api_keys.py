"""
API Key接口
"""
import secrets
import json
from datetime import datetime
from typing import Optional, List

from fastapi import APIRouter, Depends, HTTPException, status, Request
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.models.user import User
from app.models.api_key import ApiKey, ApiKeyStatus
from app.models.model_group import ModelGroup
from app.dependencies import get_current_user
from app.schemas.api_key import (
    # User-facing
    ApiKeyCreate, ApiKeyUpdate, ApiKeyResponse,
    ApiKeyListResponse, ApiKeyStatusUpdate, ApiKeyCreatedResponse,
    # Admin-facing
    ApiKeyAdminCreate, ApiKeyAdminUpdate,
    ApiKeyAdminResponse, ApiKeyAdminListResponse,
)
from app.services.operation_log_service import record_operation
from app.services.proxy_service import ProxyService, create_proxy_service
from app.utils.request import extract_client_ip

router = APIRouter()


def generate_key_id() -> str:
    """生成Key ID"""
    return f"key_{secrets.token_hex(8)}"


def generate_api_key() -> str:
    """生成API Key"""
    return f"tmk_{secrets.token_hex(16)}"


def check_and_reset_daily(api_key: ApiKey, db: Session):
    """检查并重置每日用量"""
    today = datetime.now().date()
    reset_date = api_key.daily_reset_at.date() if api_key.daily_reset_at else None
    if reset_date is None or reset_date != today:
        api_key.daily_used = 0
        api_key.daily_reset_at = datetime.now()


def check_and_reset_monthly(api_key: ApiKey, db: Session):
    """检查并重置每月用量"""
    today = datetime.now().date()
    reset_date = api_key.monthly_reset_at.date() if api_key.monthly_reset_at else None
    if reset_date is None or reset_date.month != today.month or reset_date.year != today.year:
        api_key.monthly_used = 0
        api_key.monthly_reset_at = datetime.now()


def _assign_key_groups(db: Session, api_key: ApiKey, group_ids: List[str]):
    """将模型分组关联到 API Key（内部使用）"""
    if group_ids:
        groups = db.query(ModelGroup).filter(
            ModelGroup.group_id.in_(group_ids),
            ModelGroup.status == "active"
        ).all()
        api_key.model_groups = groups
    else:
        api_key.model_groups = []


# ========== 用户接口 ==========

@router.get("", response_model=ApiKeyListResponse)
async def list_api_keys(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    获取当前用户的API Key列表
    """
    api_keys = db.query(ApiKey).filter(
        ApiKey.user_id == current_user.user_id
    ).all()
    
    for key in api_keys:
        check_and_reset_daily(key, db)
        check_and_reset_monthly(key, db)
    db.commit()
    
    # User-facing response: no model_groups
    items = [
        ApiKeyResponse(
            key_id=key.key_id,
            user_id=key.user_id,
            api_key=key.api_key,
            key_name=key.key_name,
            daily_limit=key.daily_limit,
            daily_used=key.daily_used,
            monthly_limit=key.monthly_limit,
            monthly_used=key.monthly_used,
            qps_limit=key.qps_limit,
            status=key.status.value,
            created_at=key.created_at,
            last_used_at=key.last_used_at,
        )
        for key in api_keys
    ]
    
    return ApiKeyListResponse(total=len(items), items=items)


@router.post("", response_model=ApiKeyCreatedResponse)
async def create_api_key(
    request: Request,
    api_key_data: ApiKeyCreate,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    创建新的API Key（用户）
    
    GC-1: effective groups computed via ProxyService.get_effective_model_group_ids
    """
    key_id = generate_key_id()
    api_key = generate_api_key()

    new_api_key = ApiKey(
        key_id=key_id,
        user_id=current_user.user_id,
        api_key=api_key,
        key_name=api_key_data.name,
        daily_limit=api_key_data.daily_limit,
        monthly_limit=api_key_data.monthly_limit,
        qps_limit=api_key_data.qps_limit,
        daily_reset_at=datetime.now().date(),
        monthly_reset_at=datetime.now().date(),
        status=ApiKeyStatus.active
    )

    # GC-1: use single source of truth for effective groups
    proxy_service = create_proxy_service(db)
    effective_group_ids = proxy_service.get_effective_model_group_ids(current_user)
    _assign_key_groups(db, new_api_key, list(effective_group_ids))

    db.add(new_api_key)
    db.commit()
    db.refresh(new_api_key)

    record_operation(
        db=db,
        operator=current_user,
        action="create",
        target_type="api_key",
        target_id=key_id,
        detail={
            "name": new_api_key.key_name,
            "daily_limit": new_api_key.daily_limit,
            "monthly_limit": new_api_key.monthly_limit,
            "qps_limit": new_api_key.qps_limit,
        },
        ip_address=extract_client_ip(request),
    )

    return ApiKeyCreatedResponse(
        key_id=new_api_key.key_id,
        api_key=new_api_key.api_key,
        key_name=new_api_key.key_name
    )


@router.get("/{key_id}")
async def get_api_key(
    key_id: str,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """获取单个API Key详情（用户）"""
    api_key = db.query(ApiKey).filter(
        ApiKey.key_id == key_id,
        ApiKey.user_id == current_user.user_id
    ).first()

    if not api_key:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="API Key不存在"
        )

    check_and_reset_daily(api_key, db)
    check_and_reset_monthly(api_key, db)
    db.commit()

    # User-facing: no model_groups
    return ApiKeyResponse(
        key_id=api_key.key_id,
        user_id=api_key.user_id,
        api_key=api_key.api_key,
        key_name=api_key.key_name,
        daily_limit=api_key.daily_limit,
        daily_used=api_key.daily_used,
        monthly_limit=api_key.monthly_limit,
        monthly_used=api_key.monthly_used,
        qps_limit=api_key.qps_limit,
        status=api_key.status.value,
        created_at=api_key.created_at,
        last_used_at=api_key.last_used_at,
    )


@router.put("/{key_id}")
async def update_api_key(
    request: Request,
    key_id: str,
    api_key_data: ApiKeyUpdate,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    更新API Key（用户）
    
    GC-2: no model_group_ids in user-facing update schema
    """
    api_key = db.query(ApiKey).filter(
        ApiKey.key_id == key_id,
        ApiKey.user_id == current_user.user_id
    ).first()

    if not api_key:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="API Key不存在"
        )

    changed = {}
    if api_key_data.name is not None and api_key.key_name != api_key_data.name:
        changed["name"] = api_key_data.name
        api_key.key_name = api_key_data.name
    if api_key_data.daily_limit is not None and api_key.daily_limit != api_key_data.daily_limit:
        changed["daily_limit"] = api_key_data.daily_limit
        api_key.daily_limit = api_key_data.daily_limit
    if api_key_data.monthly_limit is not None and api_key.monthly_limit != api_key_data.monthly_limit:
        changed["monthly_limit"] = api_key_data.monthly_limit
        api_key.monthly_limit = api_key_data.monthly_limit
    if api_key_data.qps_limit is not None and api_key.qps_limit != api_key_data.qps_limit:
        changed["qps_limit"] = api_key_data.qps_limit
        api_key.qps_limit = api_key_data.qps_limit
    if api_key_data.ip_whitelist is not None:
        changed["ip_whitelist"] = api_key_data.ip_whitelist
        api_key.ip_whitelist = json.dumps(api_key_data.ip_whitelist)

    db.commit()

    if changed:
        record_operation(
            db=db,
            operator=current_user,
            action="update",
            target_type="api_key",
            target_id=key_id,
            detail=changed,
            ip_address=extract_client_ip(request),
        )

    return {"message": "更新成功"}


@router.put("/{key_id}/status")
async def update_api_key_status(
    request: Request,
    key_id: str,
    status_data: ApiKeyStatusUpdate,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """启用/禁用API Key"""
    api_key = db.query(ApiKey).filter(
        ApiKey.key_id == key_id,
        ApiKey.user_id == current_user.user_id
    ).first()

    if not api_key:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="API Key不存在"
        )

    if status_data.status == "active":
        api_key.status = ApiKeyStatus.active
    elif status_data.status == "disabled":
        api_key.status = ApiKeyStatus.disabled
    else:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="无效的状态值"
        )

    db.commit()

    record_operation(
        db=db,
        operator=current_user,
        action="update_status",
        target_type="api_key",
        target_id=key_id,
        detail={"status": status_data.status},
        ip_address=extract_client_ip(request),
    )

    return {"message": "状态更新成功"}


@router.delete("/{key_id}")
async def delete_api_key(
    request: Request,
    key_id: str,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """删除API Key"""
    api_key = db.query(ApiKey).filter(
        ApiKey.key_id == key_id,
        ApiKey.user_id == current_user.user_id
    ).first()

    if not api_key:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="API Key不存在"
        )

    deleted_name = api_key.key_name
    db.delete(api_key)
    db.commit()

    record_operation(
        db=db,
        operator=current_user,
        action="delete",
        target_type="api_key",
        target_id=key_id,
        detail={"name": deleted_name},
        ip_address=extract_client_ip(request),
    )

    return {"message": "删除成功"}


# ========== 管理员接口 ==========

def _get_key_model_groups(api_key: ApiKey) -> List[str]:
    """获取API Key关联的模型分组ID列表（内部）"""
    return [g.group_id for g in api_key.model_groups]


@router.get("/admin/all", response_model=ApiKeyAdminListResponse)
async def list_all_api_keys(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """
    获取所有API Key列表（管理员）
    """
    if current_user.role != "admin":
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="权限不足"
        )
    
    api_keys = db.query(ApiKey).all()
    
    # Admin-facing: includes model_groups
    items = [
        ApiKeyAdminResponse(
            key_id=key.key_id,
            user_id=key.user_id,
            api_key=key.api_key,
            key_name=key.key_name,
            daily_limit=key.daily_limit,
            daily_used=key.daily_used,
            monthly_limit=key.monthly_limit,
            monthly_used=key.monthly_used,
            qps_limit=key.qps_limit,
            status=key.status.value,
            created_at=key.created_at,
            last_used_at=key.last_used_at,
            model_groups=_get_key_model_groups(key)
        )
        for key in api_keys
    ]
    
    return ApiKeyAdminListResponse(total=len(items), items=items)


@router.post("/admin")
async def admin_create_api_key(
    request: Request,
    api_key_data: ApiKeyAdminCreate,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    创建API Key（管理员，可为其他用户创建）
    
    Admin-facing: accepts model_group_ids and optional user_id.
    """
    if current_user.role != "admin":
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="权限不足"
        )
    
    target_user_id = api_key_data.user_id or current_user.user_id
    key_id = generate_key_id()
    api_key = generate_api_key()

    new_api_key = ApiKey(
        key_id=key_id,
        user_id=target_user_id,
        api_key=api_key,
        key_name=api_key_data.name,
        daily_limit=api_key_data.daily_limit,
        monthly_limit=api_key_data.monthly_limit,
        qps_limit=api_key_data.qps_limit,
        daily_reset_at=datetime.now().date(),
        monthly_reset_at=datetime.now().date(),
        status=ApiKeyStatus.active
    )

    group_ids = api_key_data.model_group_ids or []
    _assign_key_groups(db, new_api_key, group_ids)

    db.add(new_api_key)
    db.commit()
    db.refresh(new_api_key)

    record_operation(
        db=db,
        operator=current_user,
        action="create",
        target_type="api_key",
        target_id=key_id,
        detail={
            "name": new_api_key.key_name,
            "target_user_id": target_user_id,
            "model_group_ids": group_ids,
        },
        ip_address=extract_client_ip(request),
    )

    return ApiKeyCreatedResponse(
        key_id=new_api_key.key_id,
        api_key=new_api_key.api_key,
        key_name=new_api_key.key_name
    )


@router.get("/admin/{key_id}", response_model=ApiKeyAdminResponse)
async def admin_get_api_key(
    key_id: str,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """获取单个API Key详情（管理员）"""
    if current_user.role != "admin":
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="权限不足"
        )
    
    api_key = db.query(ApiKey).filter(ApiKey.key_id == key_id).first()

    if not api_key:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="API Key不存在"
        )

    return ApiKeyAdminResponse(
        key_id=api_key.key_id,
        user_id=api_key.user_id,
        api_key=api_key.api_key,
        key_name=api_key.key_name,
        daily_limit=api_key.daily_limit,
        daily_used=api_key.daily_used,
        monthly_limit=api_key.monthly_limit,
        monthly_used=api_key.monthly_used,
        qps_limit=api_key.qps_limit,
        status=api_key.status.value,
        created_at=api_key.created_at,
        last_used_at=api_key.last_used_at,
        model_groups=_get_key_model_groups(api_key)
    )


@router.put("/admin/{key_id}")
async def admin_update_api_key(
    request: Request,
    key_id: str,
    api_key_data: ApiKeyAdminUpdate,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    更新API Key（管理员）
    
    Admin-facing: accepts model_group_ids.
    """
    if current_user.role != "admin":
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="权限不足"
        )
    
    api_key = db.query(ApiKey).filter(ApiKey.key_id == key_id).first()

    if not api_key:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="API Key不存在"
        )

    changed = {}
    if api_key_data.name is not None and api_key.key_name != api_key_data.name:
        changed["name"] = api_key_data.name
        api_key.key_name = api_key_data.name
    if api_key_data.daily_limit is not None and api_key.daily_limit != api_key_data.daily_limit:
        changed["daily_limit"] = api_key_data.daily_limit
        api_key.daily_limit = api_key_data.daily_limit
    if api_key_data.monthly_limit is not None and api_key.monthly_limit != api_key_data.monthly_limit:
        changed["monthly_limit"] = api_key_data.monthly_limit
        api_key.monthly_limit = api_key_data.monthly_limit
    if api_key_data.qps_limit is not None and api_key.qps_limit != api_key_data.qps_limit:
        changed["qps_limit"] = api_key_data.qps_limit
        api_key.qps_limit = api_key_data.qps_limit
    if api_key_data.ip_whitelist is not None:
        changed["ip_whitelist"] = api_key_data.ip_whitelist
        api_key.ip_whitelist = json.dumps(api_key_data.ip_whitelist)

    # Admin can set model_group_ids
    if api_key_data.model_group_ids is not None:
        changed["model_group_ids"] = api_key_data.model_group_ids
        _assign_key_groups(db, api_key, api_key_data.model_group_ids)

    db.commit()

    if changed:
        record_operation(
            db=db,
            operator=current_user,
            action="update",
            target_type="api_key",
            target_id=key_id,
            detail=changed,
            ip_address=extract_client_ip(request),
        )

    return {"message": "更新成功"}


@router.post("/admin/{key_id}/set-default")
async def admin_set_key_model_groups(
    request: Request,
    key_id: str,
    group_ids_data: dict,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    管理员直接设置 API Key 的模型分组（覆盖）。
    
    Contract (for Task 2 frontend):
      POST /api-keys/admin/{key_id}/set-default
      Body: {"model_group_ids": ["group_1", "group_2"]}
      Returns: {"message": "更新成功"}
    """
    if current_user.role != "admin":
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="权限不足"
        )
    
    api_key = db.query(ApiKey).filter(ApiKey.key_id == key_id).first()
    if not api_key:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="API Key不存在"
        )
    
    group_ids = group_ids_data.get("model_group_ids", [])
    _assign_key_groups(db, api_key, group_ids)
    db.commit()
    
    record_operation(
        db=db,
        operator=current_user,
        action="set_model_groups",
        target_type="api_key",
        target_id=key_id,
        detail={"model_group_ids": group_ids},
        ip_address=extract_client_ip(request),
    )
    
    return {"message": "更新成功"}
