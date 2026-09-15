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
    ApiKeyRevokeRequest,
    # Admin-facing
    ApiKeyAdminCreate, ApiKeyAdminUpdate,
    ApiKeyAdminResponse, ApiKeyAdminListResponse,
)
from app.services.operation_log_service import record_operation
from app.services.proxy_service import ProxyService, create_proxy_service
from app.utils.request import extract_client_ip
from datetime import datetime

router = APIRouter()


def generate_key_id() -> str:
    """生成Key ID"""
    return f"key_{secrets.token_hex(8)}"


def generate_api_key() -> str:
    """生成API Key"""
    return f"tmk_{secrets.token_hex(16)}"


def _parse_ip_whitelist(value: Optional[str]) -> List[str]:
    if not value:
        return []
    try:
        parsed = json.loads(value)
        return parsed if isinstance(parsed, list) else []
    except json.JSONDecodeError:
        return []


def _api_key_response(key: ApiKey, admin: bool = False):
    response_cls = ApiKeyAdminResponse if admin else ApiKeyResponse
    return response_cls(
        key_id=key.key_id,
        user_id=key.user_id,
        api_key=key.api_key,
        name=key.key_name,
        status=key.status.value,
        created_at=key.created_at,
        last_used_at=key.last_used_at,
        ip_whitelist=_parse_ip_whitelist(key.ip_whitelist),
        expires_at=key.expires_at,
        revoked_at=key.revoked_at,
        revoked_reason=key.revoked_reason,
        last_used_ip=key.last_used_ip,
        last_used_user_agent=key.last_used_user_agent,
    )


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

    items = [_api_key_response(key) for key in api_keys]
    
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
        ip_whitelist=json.dumps(api_key_data.ip_whitelist or []),
        expires_at=api_key_data.expires_at,
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
        expires_at=new_api_key.expires_at,
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
    if "expires_at" in api_key_data.model_fields_set:
        changed["expires_at"] = api_key_data.expires_at.isoformat() if api_key_data.expires_at else None
        api_key.expires_at = api_key_data.expires_at

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


@router.put("/{key_id}/revoke")
async def revoke_api_key(
    request: Request,
    key_id: str,
    revoke_data: ApiKeyRevokeRequest,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """吊销API Key"""
    api_key = db.query(ApiKey).filter(
        ApiKey.key_id == key_id,
        ApiKey.user_id == current_user.user_id
    ).first()

    if not api_key:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="API Key不存在")

    api_key.status = ApiKeyStatus.revoked
    api_key.revoked_at = datetime.utcnow()
    api_key.revoked_reason = revoke_data.reason
    db.commit()

    record_operation(
        db=db,
        operator=current_user,
        action="revoke",
        target_type="api_key",
        target_id=key_id,
        detail={"reason": revoke_data.reason},
        ip_address=extract_client_ip(request),
    )

    return {"message": "吊销成功"}


@router.post("/{key_id}/rotate", response_model=ApiKeyCreatedResponse)
async def rotate_api_key(
    request: Request,
    key_id: str,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """轮换API Key：生成新密钥，旧密钥立即失效。"""
    api_key = db.query(ApiKey).filter(
        ApiKey.key_id == key_id,
        ApiKey.user_id == current_user.user_id
    ).first()

    if not api_key:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="API Key不存在")

    old_fingerprint = api_key.api_key[-6:]
    api_key.api_key = generate_api_key()
    api_key.status = ApiKeyStatus.active
    api_key.revoked_at = None
    api_key.revoked_reason = None
    db.commit()
    db.refresh(api_key)

    record_operation(
        db=db,
        operator=current_user,
        action="rotate",
        target_type="api_key",
        target_id=key_id,
        detail={"old_key_suffix": old_fingerprint},
        ip_address=extract_client_ip(request),
    )

    return ApiKeyCreatedResponse(
        key_id=api_key.key_id,
        api_key=api_key.api_key,
        name=api_key.key_name,
        expires_at=api_key.expires_at,
    )


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
    
    items = [_api_key_response(key, admin=True) for key in api_keys]
    
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
        ip_whitelist=json.dumps(api_key_data.ip_whitelist or []),
        expires_at=api_key_data.expires_at,
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
        expires_at=new_api_key.expires_at,
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

    return _api_key_response(api_key, admin=True)


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
    if "expires_at" in api_key_data.model_fields_set:
        changed["expires_at"] = api_key_data.expires_at.isoformat() if api_key_data.expires_at else None
        api_key.expires_at = api_key_data.expires_at

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


@router.put("/admin/{key_id}/revoke")
async def admin_revoke_api_key(
    request: Request,
    key_id: str,
    revoke_data: ApiKeyRevokeRequest,
    current_user: User = Depends(require_admin),
    db: Session = Depends(get_db)
):
    """吊销API Key（管理员）"""
    api_key = db.query(ApiKey).filter(ApiKey.key_id == key_id).first()
    if not api_key:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="API Key不存在")

    api_key.status = ApiKeyStatus.revoked
    api_key.revoked_at = datetime.utcnow()
    api_key.revoked_reason = revoke_data.reason
    db.commit()

    record_operation(
        db=db,
        operator=current_user,
        action="revoke",
        target_type="api_key",
        target_id=key_id,
        detail={"reason": revoke_data.reason},
        ip_address=extract_client_ip(request),
    )

    return {"message": "吊销成功"}


@router.post("/admin/{key_id}/rotate", response_model=ApiKeyCreatedResponse)
async def admin_rotate_api_key(
    request: Request,
    key_id: str,
    current_user: User = Depends(require_admin),
    db: Session = Depends(get_db)
):
    """轮换API Key（管理员）"""
    api_key = db.query(ApiKey).filter(ApiKey.key_id == key_id).first()
    if not api_key:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="API Key不存在")

    old_fingerprint = api_key.api_key[-6:]
    api_key.api_key = generate_api_key()
    api_key.status = ApiKeyStatus.active
    api_key.revoked_at = None
    api_key.revoked_reason = None
    db.commit()
    db.refresh(api_key)

    record_operation(
        db=db,
        operator=current_user,
        action="rotate",
        target_type="api_key",
        target_id=key_id,
        detail={"old_key_suffix": old_fingerprint},
        ip_address=extract_client_ip(request),
    )

    return ApiKeyCreatedResponse(
        key_id=api_key.key_id,
        api_key=api_key.api_key,
        name=api_key.key_name,
        expires_at=api_key.expires_at,
    )


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
