"""
模型分组服务 — 默认组切换、迁移等。

提取 set/unset default 的事务逻辑，保证 §2.2（唯一默认组）+ §2.10/§2.11（不补绑/不清绑）。
"""
from sqlalchemy.orm import Session
from fastapi import HTTPException, status

from app.models.model_group import ModelGroup, ModelGroupStatus


def set_default_group(db: Session, group_id: str) -> ModelGroup:
    """
    事务性将指定分组设为唯一默认分组：
    - 清除其他分组的 is_default
    - 设置本组的 is_default=1
    - 不补绑历史模型（§2.10）
    """
    group = db.query(ModelGroup).filter(ModelGroup.group_id == group_id).first()
    if not group:
        raise HTTPException(status.HTTP_404_NOT_FOUND, detail="模型分组不存在")
    if group.status != ModelGroupStatus.active:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, detail="禁用的分组不能设为默认")

    db.query(ModelGroup).update({ModelGroup.is_default: 0})
    group.is_default = 1
    db.commit()
    db.refresh(group)
    return group


def unset_default_group(db: Session, group_id: str) -> ModelGroup:
    """
    取消默认分组状态。不删除已有模型绑定（§2.11）。
    """
    group = db.query(ModelGroup).filter(ModelGroup.group_id == group_id).first()
    if not group:
        raise HTTPException(status.HTTP_404_NOT_FOUND, detail="模型分组不存在")
    group.is_default = 0
    db.commit()
    db.refresh(group)
    return group
