"""模型分组权限申请的审批生效动作。"""
import json

from fastapi import HTTPException

from app.models.model_group import ModelGroup, ModelGroupStatus
from app.models.user import User


def apply_model_group_approval(db, request):
    group_id = request.payload.get('group_id')
    group = db.query(ModelGroup).filter_by(group_id=group_id).first()
    if group is None:
        raise HTTPException(404, '模型分组不存在')
    if group.status != ModelGroupStatus.active:
        raise HTTPException(409, '模型分组已停用，不能授予权限')

    user = db.query(User).filter_by(user_id=request.requester_user_id).first()
    if user is None:
        raise HTTPException(404, '申请用户不存在')
    group_ids = json.loads(user.model_group_ids or '[]')
    if group_id not in group_ids:
        group_ids.append(group_id)
        user.model_group_ids = json.dumps(group_ids)
        db.add(user)
