"""
API Key接口
"""
import secrets
import json
from datetime import datetime
from typing import Optional, List

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.models.user import User
from app.models.api_key import ApiKey, ApiKeyStatus
from app.models.model_group import ModelGroup
from app.dependencies import get_current_user
from app.schemas.api_key import (
    ApiKeyCreate, ApiKeyUpdate, ApiKeyResponse,
    ApiKeyListResponse, ApiKeyStatusUpdate, ApiKeyCreatedResponse
)

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
    if api_key.daily_reset_at is None or api_key.daily_reset_at != today:
        api_key.daily_used = 0
        api_key.daily_reset_at = today


def check_and_reset_monthly(api_key: ApiKey, db: Session):
    """检查并重置每月用量"""
    today = datetime.now().date()
    if api_key.monthly_reset_at is None or api_key.monthly_reset_at.month != today.month:
        api_key.monthly_used = 0
        api_key.monthly_reset_at = today


def get_key_model_groups(api_key: ApiKey) -> List[str]:
    """获取API Key关联的模型分组ID列表"""
    return [g.group_id for g in api_key.model_groups]


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
    
    # 检查并重置用量
    for key in api_keys:
        check_and_reset_daily(key, db)
        check_and_reset_monthly(key, db)
    db.commit()
    
    items = [
        ApiKeyResponse(
            key_id=key.key_id,
            user_id=key.user_id,
            api_key=key.api_key,
            name=key.key_name,
            daily_limit=key.daily_limit,
            daily_used=key.daily_used,
            monthly_limit=key.monthly_limit,
            monthly_used=key.monthly_used,
            qps_limit=key.qps_limit,
            status=key.status.value,
            created_at=key.created_at,
            last_used_at=key.last_used_at,
            model_groups=get_key_model_groups(key)
        )
        for key in api_keys
    ]
    
    return ApiKeyListResponse(total=len(items), items=items)


@router.post("", response_model=ApiKeyCreatedResponse)
async def create_api_key(
    api_key_data: ApiKeyCreate,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    创建新的API Key
    """
    # 生成Key ID和API Key
    key_id = generate_key_id()
    api_key = generate_api_key()
    
    # 创建记录
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
    
    # 关联模型分组
    # 如果没有提供 model_group_ids（普通用户），则使用用户被分配的模型分组
    group_ids = api_key_data.model_group_ids
    if not group_ids:
        import json
        group_ids = json.loads(current_user.model_group_ids or '[]')
    
    if group_ids:
        groups = db.query(ModelGroup).filter(
            ModelGroup.group_id.in_(group_ids)
        ).all()
        new_api_key.model_groups = groups
    
    db.add(new_api_key)
    db.commit()
    db.refresh(new_api_key)
    
    return ApiKeyCreatedResponse(
        key_id=new_api_key.key_id,
        api_key=new_api_key.api_key,
        key_name=new_api_key.key_name
    )


@router.get("/{key_id}", response_model=ApiKeyResponse)
async def get_api_key(
    key_id: str,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    获取指定API Key详情
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
    
    # 检查并重置用量
    check_and_reset_daily(api_key, db)
    check_and_reset_monthly(api_key, db)
    db.commit()
    
    return ApiKeyResponse(
        key_id=api_key.key_id,
        user_id=api_key.user_id,
        api_key=api_key.api_key,
        name=api_key.key_name,
        daily_limit=api_key.daily_limit,
        daily_used=api_key.daily_used,
        monthly_limit=api_key.monthly_limit,
        monthly_used=api_key.monthly_used,
        qps_limit=api_key.qps_limit,
        status=api_key.status.value,
        created_at=api_key.created_at,
        last_used_at=api_key.last_used_at,
        model_groups=get_key_model_groups(api_key)
    )


@router.put("/{key_id}")
async def update_api_key(
    key_id: str,
    api_key_data: ApiKeyUpdate,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    更新API Key
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
    
    # 更新字段
    if api_key_data.name is not None:
        api_key.key_name = api_key_data.name
    if api_key_data.daily_limit is not None:
        api_key.daily_limit = api_key_data.daily_limit
    if api_key_data.monthly_limit is not None:
        api_key.monthly_limit = api_key_data.monthly_limit
    if api_key_data.qps_limit is not None:
        api_key.qps_limit = api_key_data.qps_limit
    if api_key_data.ip_whitelist is not None:
        api_key.ip_whitelist = json.dumps(api_key_data.ip_whitelist)
    
    # 更新模型分组关联
    if api_key_data.model_group_ids is not None:
        groups = db.query(ModelGroup).filter(
            ModelGroup.group_id.in_(api_key_data.model_group_ids)
        ).all()
        api_key.model_groups = groups
    
    db.commit()
    
    return {"message": "更新成功"}


@router.put("/{key_id}/status")
async def update_api_key_status(
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
    
    return {"message": "状态更新成功"}


@router.delete("/{key_id}")
async def delete_api_key(
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
    
    return {"message": "删除成功"}


# ========== 管理员接口 ==========

@router.get("/admin/all", response_model=ApiKeyListResponse)
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
    
    items = [
        ApiKeyResponse(
            key_id=key.key_id,
            user_id=key.user_id,
            api_key=key.api_key,
            name=key.key_name,
            daily_limit=key.daily_limit,
            daily_used=key.daily_used,
            monthly_limit=key.monthly_limit,
            monthly_used=key.monthly_used,
            qps_limit=key.qps_limit,
            status=key.status.value,
            created_at=key.created_at,
            last_used_at=key.last_used_at,
            model_groups=get_key_model_groups(key)
        )
        for key in api_keys
    ]
    
    return ApiKeyListResponse(total=len(items), items=items)
