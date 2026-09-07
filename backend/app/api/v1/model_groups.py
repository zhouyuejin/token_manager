"""
模型分组管理API

§13 Task 5: provider_ids → model_ids；CRUD 仅管理员；模型 ID 校验/去重/事务处理；
删除分组时清理用户 JSON 中的 group_id。
"""
import json
import secrets
from typing import Optional, List

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.models.user import User
from app.models.model_group import ModelGroup, ModelGroupStatus, model_group_model_mappings
from app.models.model_mapping import ModelMapping
from app.dependencies import get_current_user, require_admin
from app.schemas.model_group import (
    ModelGroupCreate, ModelGroupUpdate, ModelGroupResponse,
    ModelGroupListResponse
)

router = APIRouter()


def _get_model_ids_from_group(group: ModelGroup) -> List[str]:
    """从 group 对象提取绑定的 model_id 列表"""
    return [m.model_id for m in group.model_mappings]


def _sync_model_bindings(db: Session, group: ModelGroup, model_ids: Optional[List[str]]) -> List[str]:
    """
    原子性同步分组与模型的绑定关系。
    
    - model_ids 为 None 时不修改绑定
    - 去重后校验每个 model_id 是否存在
    - 允许绑定 disabled 模型（但不可用）
    - 返回最终绑定的 model_id 列表
    """
    if model_ids is None:
        return _get_model_ids_from_group(group)
    
    # 去重
    unique_ids = list(set(model_ids))
    
    # 校验每个 model_id 存在
    if unique_ids:
        existing = db.query(ModelMapping.model_id).filter(
            ModelMapping.model_id.in_(unique_ids)
        ).all()
        existing_set = {row[0] for row in existing}
        missing = set(unique_ids) - existing_set
        if missing:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"模型不存在: {', '.join(sorted(missing))}"
            )
    
    # 重新构建绑定关系
    group.model_mappings.clear()
    if unique_ids:
        models = db.query(ModelMapping).filter(
            ModelMapping.model_id.in_(unique_ids)
        ).all()
        group.model_mappings.extend(models)
    
    return unique_ids


def _cleanup_users_with_group(db: Session, group_id: str) -> int:
    """
    删除分组后，清理所有用户 JSON 中的 group_id。
    返回清理的用户数。
    """
    from app.models.user import User
    import json
    
    users = db.query(User).all()
    cleaned = 0
    for user in users:
        if not user.model_group_ids:
            continue
        try:
            group_ids = json.loads(user.model_group_ids)
        except (json.JSONDecodeError, TypeError):
            group_ids = []
        
        if group_id in group_ids:
            group_ids.remove(group_id)
            user.model_group_ids = json.dumps(group_ids)
            cleaned += 1
    
    if cleaned > 0:
        db.commit()
    return cleaned


@router.get("", response_model=ModelGroupListResponse)
async def list_model_groups(
    db: Session = Depends(get_db),
    current_user: User = Depends(require_admin)  # §13 Task 5: 仅管理员可访问
):
    """
    获取模型分组列表（仅管理员）
    """
    groups = db.query(ModelGroup).all()
    
    items = []
    for g in groups:
        model_ids = _get_model_ids_from_group(g)
        items.append(ModelGroupResponse(
            group_id=g.group_id,
            name=g.name,
            description=g.description,
            status=g.status.value,
            is_default=g.is_default,
            model_ids=model_ids,
            created_at=g.created_at
        ))
    
    return ModelGroupListResponse(total=len(items), items=items)


@router.post("", response_model=ModelGroupResponse)
async def create_model_group(
    group_data: ModelGroupCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_admin)
):
    """
    创建模型分组（仅管理员）
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
    db.flush()  # 获取 group.id 用于后续关联
    
    # 绑定模型（如果有）
    model_ids = []
    if group_data.model_ids:
        model_ids = _sync_model_bindings(db, group, group_data.model_ids)
    
    db.commit()
    db.refresh(group)
    
    return ModelGroupResponse(
        group_id=group.group_id,
        name=group.name,
        description=group.description,
        status=group.status.value,
        is_default=group.is_default,
        model_ids=model_ids,
        created_at=group.created_at
    )


@router.get("/{group_id}", response_model=ModelGroupResponse)
async def get_model_group(
    group_id: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_admin)  # §13 Task 5: 仅管理员
):
    """
    获取模型分组详情（仅管理员）
    """
    group = db.query(ModelGroup).filter(
        ModelGroup.group_id == group_id
    ).first()
    
    if not group:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="模型分组不存在"
        )
    
    model_ids = _get_model_ids_from_group(group)
    
    return ModelGroupResponse(
        group_id=group.group_id,
        name=group.name,
        description=group.description,
        status=group.status.value,
        is_default=group.is_default,
        model_ids=model_ids,
        created_at=group.created_at
    )


@router.put("/{group_id}", response_model=ModelGroupResponse)
async def update_model_group(
    group_id: str,
    group_data: ModelGroupUpdate,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_admin)
):
    """
    更新模型分组（仅管理员）
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
    
    # 更新关联模型
    if group_data.model_ids is not None:
        _sync_model_bindings(db, group, group_data.model_ids)
    
    db.commit()
    db.refresh(group)
    
    model_ids = _get_model_ids_from_group(group)
    
    return ModelGroupResponse(
        group_id=group.group_id,
        name=group.name,
        description=group.description,
        status=group.status.value,
        is_default=group.is_default,
        model_ids=model_ids,
        created_at=group.created_at
    )


@router.delete("/{group_id}")
async def delete_model_group(
    group_id: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_admin)
):
    """
    删除模型分组（仅管理员）
    §13 Task 5: 删除前检查是否有模型正在使用该分组，如有则拒绝删除（方案A）。
    删除后清理用户 JSON 中的 group_id。
    """
    group = db.query(ModelGroup).filter(
        ModelGroup.group_id == group_id
    ).first()
    
    if not group:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="模型分组不存在"
        )
    
    # §12 方案A：检查是否有模型绑定了该分组，拒绝删除
    if group.model_mappings:
        bound_models = [m.model_id for m in group.model_mappings]
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"该分组已绑定 {len(bound_models)} 个模型，请先解除绑定后再删除"
        )
    
    # 清理用户 JSON 中的 group_id
    cleaned = _cleanup_users_with_group(db, group_id)
    
    db.delete(group)
    db.commit()
    
    return {
        "message": "删除成功",
        "cleaned_users": cleaned
    }


@router.post("/{group_id}/set-default")
async def set_model_group_as_default(
    group_id: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_admin),
):
    """
    将指定分组设为唯一默认分组（管理员）。
    事务性清除其他分组的默认状态（§2.2）；不补绑历史模型（§2.10）。
    """
    from app.services.model_groups_service import set_default_group
    set_default_group(db, group_id)
    return {"message": "已设为默认分组"}


@router.post("/{group_id}/unset-default")
async def unset_model_group_default(
    group_id: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_admin),
):
    """
    取消默认分组状态（管理员）。不清除已有模型绑定（§2.11）。
    """
    from app.services.model_groups_service import unset_default_group
    unset_default_group(db, group_id)
    return {"message": "已取消默认分组"}


# ============ 旧接口，迁移后保留兼容或删除 ============

@router.get("/providers/{provider_id}", response_model=ModelGroupListResponse)
async def get_groups_by_provider(
    provider_id: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_admin)  # §13 Task 5: 仅管理员
):
    """
    获取指定供应商关联的模型分组（仅管理员）
    注意：此接口基于旧 provider 关联，返回结果可能不完整。
    建议使用按模型查询的接口。
    """
    # 不再推荐使用，基于 provider 过滤不可靠
    # 返回所有分组，由前端按需过滤
    groups = db.query(ModelGroup).all()
    
    items = []
    for g in groups:
        # 检查分组中是否有来自该供应商的模型
        model_ids = _get_model_ids_from_group(g)
        if not model_ids:
            continue
        models_from_provider = db.query(ModelMapping).filter(
            ModelMapping.model_id.in_(model_ids),
            ModelMapping.provider_id == provider_id
        ).count()
        if models_from_provider == 0:
            continue
            
        items.append(ModelGroupResponse(
            group_id=g.group_id,
            name=g.name,
            description=g.description,
            status=g.status.value,
            is_default=g.is_default,
            model_ids=model_ids,
            created_at=g.created_at
        ))
    
    return ModelGroupListResponse(total=len(items), items=items)
