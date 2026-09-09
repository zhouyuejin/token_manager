"""
API Key接口

Task 5: 删除所有 model_group_ids / model_groups 相关代码。
API Key 不再保留独立分组权限，统一由用户分组决定（§2.15）。
"""
import secrets
import json
from typing import Optional, List

from fastapi import APIRouter, Depends, HTTPException, status, Request
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.models.user import User
from app.models.api_key import ApiKey, ApiKeyStatus
from app.dependencies import get_current_user, require_admin
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

    items = [
        ApiKeyResponse(
            key_id=key.key_id,
            user_id=key.user_id,
            api_key=key.api_key,
            name=key.key_name,
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
    
    权限由用户所属模型分组决定，不在 API Key 层独立配置。
    """
    key_id = generate_key_id()
    api_key = generate_api_key()

    new_api_key = ApiKey(
        key_id=key_id,
        user_id=current_user.user_id,
        api_key=api_key,
        key_name=api_key_data.name,
        status=ApiKeyStatus.active
    )

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
        },
        ip_address=extract_client_ip(request),
    )

    return ApiKeyCreatedResponse(
        key_id=new_api_key.key_id,
        api_key=new_api_key.api_key,
        name=new_api_key.key_name,
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
    if api_key_data.name is not None:
        changed["name"] = api_key_data.name
        api_key.key_name = api_key_data.name
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


@router.put("/{key_id}/status", response_model=ApiKeyStatusUpdate)
async def update_api_key_status(
    request: Request,
    key_id: str,
    status_data: ApiKeyStatusUpdate,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    启用/禁用API Key
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

    old_status = api_key.status.value
    api_key.status = ApiKeyStatus(status_data.status)
    db.commit()

    record_operation(
        db=db,
        operator=current_user,
        action="update_status",
        target_type="api_key",
        target_id=key_id,
        detail={"old": old_status, "new": status_data.status},
        ip_address=extract_client_ip(request),
    )

    return {"status": status_data.status}


@router.delete("/{key_id}")
async def delete_api_key(
    request: Request,
    key_id: str,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    删除API Key
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

    db.delete(api_key)
    db.commit()

    record_operation(
        db=db,
        operator=current_user,
        action="delete",
        target_type="api_key",
        target_id=key_id,
        detail={"name": api_key.key_name},
        ip_address=extract_client_ip(request),
    )

    return {"message": "删除成功"}


# ========== 管理员接口 ==========

@router.get("/admin", response_model=ApiKeyAdminListResponse)
async def admin_list_api_keys(
    current_user: User = Depends(require_admin),
    db: Session = Depends(get_db),
    user_id: Optional[str] = None
):
    """
    获取所有API Key列表（管理员）
    可按 user_id 过滤
    """
    query = db.query(ApiKey)
    if user_id:
        query = query.filter(ApiKey.user_id == user_id)
    
    api_keys = query.all()
    
    items = [
        ApiKeyAdminResponse(
            key_id=key.key_id,
            user_id=key.user_id,
            api_key=key.api_key,
            name=key.key_name,
            status=key.status.value,
            created_at=key.created_at,
            last_used_at=key.last_used_at,
        )
        for key in api_keys
    ]
    
    return ApiKeyAdminListResponse(total=len(items), items=items)


@router.post("/admin", response_model=ApiKeyCreatedResponse)
async def admin_create_api_key(
    request: Request,
    api_key_data: ApiKeyAdminCreate,
    current_user: User = Depends(require_admin),
    db: Session = Depends(get_db)
):
    """
    创建API Key（管理员）
    权限由目标用户所属模型分组决定，不在 API Key 层独立配置。
    """
    key_id = generate_key_id()
    api_key = generate_api_key()
    
    # 如果指定了 user_id，则为该用户创建；否则为管理员自己创建
    target_user_id = api_key_data.user_id or current_user.user_id

    new_api_key = ApiKey(
        key_id=key_id,
        user_id=target_user_id,
        api_key=api_key,
        key_name=api_key_data.name,
        status=ApiKeyStatus.active
    )

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
        },
        ip_address=extract_client_ip(request),
    )

    return ApiKeyCreatedResponse(
        key_id=new_api_key.key_id,
        api_key=new_api_key.api_key,
        name=new_api_key.key_name,
    )


@router.get("/admin/{key_id}", response_model=ApiKeyAdminResponse)
async def admin_get_api_key(
    key_id: str,
    current_user: User = Depends(require_admin),
    db: Session = Depends(get_db)
):
    """获取单个API Key详情（管理员）"""
    
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
        name=api_key.key_name,
        status=api_key.status.value,
        created_at=api_key.created_at,
        last_used_at=api_key.last_used_at,
    )


@router.put("/admin/{key_id}")
async def admin_update_api_key(
    request: Request,
    key_id: str,
    api_key_data: ApiKeyAdminUpdate,
    current_user: User = Depends(require_admin),
    db: Session = Depends(get_db)
):
    """
    更新API Key（管理员）
    """
    
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


@router.delete("/admin/{key_id}")
async def admin_delete_api_key(
    request: Request,
    key_id: str,
    current_user: User = Depends(require_admin),
    db: Session = Depends(get_db)
):
    """
    删除API Key（管理员）
    """
    
    api_key = db.query(ApiKey).filter(ApiKey.key_id == key_id).first()

    if not api_key:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="API Key不存在"
        )

    db.delete(api_key)
    db.commit()

    record_operation(
        db=db,
        operator=current_user,
        action="delete",
        target_type="api_key",
        target_id=key_id,
        detail={"name": api_key.key_name},
        ip_address=extract_client_ip(request),
    )

    return {"message": "删除成功"}
