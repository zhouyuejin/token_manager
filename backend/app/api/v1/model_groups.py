"""
模型分组管理API
"""
import json
import secrets
from typing import Optional, List

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.models.user import User
from app.models.model_group import ModelGroup, ModelGroupStatus, provider_model_groups
from app.models.provider import Provider
from app.dependencies import get_current_user, require_admin
from app.schemas.model_group import (
    ModelGroupCreate, ModelGroupUpdate, ModelGroupResponse,
    ModelGroupListResponse
)

router = APIRouter()


@router.get("", response_model=ModelGroupListResponse)
async def list_model_groups(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """
    获取模型分组列表（所有登录用户可读）
    """
    groups = db.query(ModelGroup).all()
    
    items = []
    for g in groups:
        # 获取关联的供应商ID列表
        provider_ids = [p.provider_id for p in g.providers]
        items.append(ModelGroupResponse(
            group_id=g.group_id,
            name=g.name,
            description=g.description,
            status=g.status.value,
            is_default=g.is_default,
            provider_ids=provider_ids,
            created_at=g.created_at
        ))
    
    return ModelGroupListResponse(total=len(items), items=items)


@router.post("", response_model=ModelGroupResponse)
async def create_model_group(
    group_data: ModelGroupCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """
    创建模型分组（管理员）
    """
    group_id = f"mg_{secrets.token_hex(8)}"
    
    # 创建分组
    group = ModelGroup(
        group_id=group_id,
        name=group_data.name,
        description=group_data.description,
        is_default=group_data.is_default or 0,
        status=ModelGroupStatus.active
    )
    
    db.add(group)
    
    # 关联供应商
    if group_data.provider_ids:
        providers = db.query(Provider).filter(
            Provider.provider_id.in_(group_data.provider_ids)
        ).all()
        group.providers = providers
    
    db.commit()
    db.refresh(group)
    
    return ModelGroupResponse(
        group_id=group.group_id,
        name=group.name,
        description=group.description,
        status=group.status.value,
        is_default=group.is_default,
        provider_ids=group_data.provider_ids or [],
        created_at=group.created_at
    )


@router.get("/{group_id}", response_model=ModelGroupResponse)
async def get_model_group(
    group_id: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """
    获取模型分组详情（管理员）
    """
    group = db.query(ModelGroup).filter(
        ModelGroup.group_id == group_id
    ).first()
    
    if not group:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="模型分组不存在"
        )
    
    provider_ids = [p.provider_id for p in group.providers]
    
    return ModelGroupResponse(
        group_id=group.group_id,
        name=group.name,
        description=group.description,
        status=group.status.value,
        is_default=group.is_default,
        provider_ids=provider_ids,
        created_at=group.created_at
    )


@router.put("/{group_id}", response_model=ModelGroupResponse)
async def update_model_group(
    group_id: str,
    group_data: ModelGroupUpdate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """
    更新模型分组（管理员）
    """
    group = db.query(ModelGroup).filter(
        ModelGroup.group_id == group_id
    ).first()
    
    if not group:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="模型分组不存在"
        )
    
    # 更新字段
    if group_data.name is not None:
        group.name = group_data.name
    if group_data.description is not None:
        group.description = group_data.description
    if group_data.status is not None:
        group.status = ModelGroupStatus(group_data.status)
    if group_data.is_default is not None:
        group.is_default = group_data.is_default
    
    # 更新关联供应商
    if group_data.provider_ids is not None:
        providers = db.query(Provider).filter(
            Provider.provider_id.in_(group_data.provider_ids)
        ).all()
        group.providers = providers
    
    db.commit()
    db.refresh(group)
    
    provider_ids = [p.provider_id for p in group.providers]
    
    return ModelGroupResponse(
        group_id=group.group_id,
        name=group.name,
        description=group.description,
        status=group.status.value,
        is_default=group.is_default,
        provider_ids=provider_ids,
        created_at=group.created_at
    )


@router.delete("/{group_id}")
async def delete_model_group(
    group_id: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """
    删除模型分组（管理员）
    """
    group = db.query(ModelGroup).filter(
        ModelGroup.group_id == group_id
    ).first()
    
    if not group:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="模型分组不存在"
        )
    
    db.delete(group)
    db.commit()
    
    return {"message": "删除成功"}


@router.get("/providers/{provider_id}", response_model=ModelGroupListResponse)
async def get_groups_by_provider(
    provider_id: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """
    获取指定供应商关联的模型分组
    """
    provider = db.query(Provider).filter(
        Provider.provider_id == provider_id
    ).first()
    
    if not provider:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="供应商不存在"
        )
    
    groups = provider.model_groups
    
    items = []
    for g in groups:
        provider_ids = [p.provider_id for p in g.providers]
        items.append(ModelGroupResponse(
            group_id=g.group_id,
            name=g.name,
            description=g.description,
            status=g.status.value,
            is_default=g.is_default,
            provider_ids=provider_ids,
            created_at=g.created_at
        ))
    
    return ModelGroupListResponse(total=len(items), items=items)


@router.post("/{group_id}/set-default")
async def set_model_group_as_default(
    group_id: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_admin),
):
    """
    将指定模型分组设为默认分组（管理员）。
    多个分组可同时为默认分组（GC-6）。
    """
    group = db.query(ModelGroup).filter(
        ModelGroup.group_id == group_id
    ).first()

    if not group:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="模型分组不存在"
        )

    group.is_default = 1
    db.commit()

    return {"message": "已设为默认分组"}


@router.post("/{group_id}/unset-default")
async def unset_model_group_default(
    group_id: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_admin),
):
    """
    取消指定模型分组的默认分组状态（管理员）。
    """
    group = db.query(ModelGroup).filter(
        ModelGroup.group_id == group_id
    ).first()

    if not group:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="模型分组不存在"
        )

    group.is_default = 0
    db.commit()

    return {"message": "已取消默认分组"}
